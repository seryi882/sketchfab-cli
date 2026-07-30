#!/usr/bin/env node
/**
 * Sketchfab .binz decryptor (WASM path).
 *
 * Usage:
 *   node decrypt_worker.mjs <work_dir> <key1_base64_or_@keyfile> [static_key_hex]
 *
 * Reads *.binz in work_dir, writes:
 *   file.binz              -> file.osgjs
 *   model_file.binz        -> model_file.bin
 *   model_file_wireframe.binz -> model_file_wireframe.bin
 *   other X.binz           -> X (without .binz) or X.bin / X.osgjs by name
 *
 * Based on community WASM decrypt flow (static 40-hex key + per-model diter.b).
 */
import fs from "fs";
import path from "path";
import zlib from "zlib";
import { fileURLToPath } from "url";
import { createRequire } from "module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Fallback only — prefer key extracted from current viewer JS.
const DEFAULT_STATIC_KEY = "7d61ef7c7530c12cf080fafd05e603d1aa3a92c6";

function parseWasmDataSize(wasmBytes) {
  let m = 65536;
  let d = 8;
  while (d < wasmBytes.length) {
    const v = () => wasmBytes[d++];
    const w = () => {
      let t = d,
        n = 0,
        e = 128;
      while (128 & e) {
        e = wasmBytes[d];
        n |= (127 & e) << (7 * (d - t));
        d++;
      }
      return n;
    };
    let y = w(),
      I = w(),
      h = d + I;
    if (y < 0 || y > 11 || I <= 0 || h > wasmBytes.length) break;
    if (6 === y) {
      w();
      v();
      v();
      w();
      let _ = w();
      w();
      m = _;
    }
    if (11 === y) {
      for (let Z = w(), A = 0; A !== Z && d < h; A++) {
        v();
        w();
        w();
        w();
        let U = w();
        d += U;
      }
    }
    d = h;
  }
  return m;
}

async function initWasm(wasmBytes) {
  const r = new Uint8Array(wasmBytes);
  const m = parseWasmDataSize(r);
  const u = 536870912;
  const g = 262144 + (((m + 65535) >> 16) << 16);
  let currentBreak = m;

  const memory = new WebAssembly.Memory({
    initial: g >> 16,
    maximum: u >> 16,
    shared: false,
  });
  let uint8View = new Uint8Array(memory.buffer);
  let uint32View = new Uint32Array(memory.buffer);

  function refreshViews() {
    uint8View = new Uint8Array(memory.buffer);
    uint32View = new Uint32Array(memory.buffer);
  }

  const env = {
    sbrk(increment) {
      const old = currentBreak;
      const newBreak = old + increment;
      const overflow = newBreak - memory.buffer.byteLength;
      if (overflow > 0) {
        memory.grow((overflow + 65535) >> 16);
        refreshViews();
      }
      currentBreak = newBreak;
      return old | 0;
    },
    time(t) {
      const r = (Date.now() / 1000) | 0;
      if (t) uint32View[t >> 2] = r;
      return r;
    },
    gettimeofday(t) {
      const n = Date.now();
      uint32View[t >> 2] = (n / 1000) | 0;
      uint32View[(t + 4) >> 2] = (n % 1000) * 1000;
    },
    abort() {
      throw new Error("WASM abort");
    },
    memory,
  };
  env.__lock = env.__unlock = env.setjmp = env.__cxa_atexit = function () {};

  const result = await WebAssembly.instantiate(r, { env });
  const ex = result.instance.exports;
  if (ex.__wasm_call_ctors) ex.__wasm_call_ctors();
  return {
    a: ex,
    H: () => {
      refreshViews();
      return uint8View;
    },
  };
}

async function decryptBinz(wasmBytes, encData, diterB, staticKey) {
  const wasm = await initWasm(wasmBytes);
  const a = wasm.a;

  const allocInput = a["heSBnb29kYnllCk5ldmVyIGdvbm5hIHRl"];
  const reset = a["mV2ZXIgZ29ubmEgbGV0IHlvdSBkb3duCk5l"];
  const rickRolled = a["Umlja1JvbGxlZDRV"];
  const allocDiterB = a["dmVyIGdvbm5hIHJ1biBhcm91bmQgYW5kI"];
  const process_ = a["GRlc2VydCB5b3UKTmV2ZXIgZ29ubmEgbW"];
  const advance = a["FrZSB5b3UgY3J5Ck5ldmVyIGdvbm5hIHN"];
  const getInfo = a["bGwgYSBsaWUgYW5kIGh1cnQgeW91Cg"];
  const getStart = a["TmV2ZXIgZ29ubmEgZ2l2ZSB5b3UgdXAKT"];

  if (
    !allocInput ||
    !reset ||
    !rickRolled ||
    !allocDiterB ||
    !process_ ||
    !advance ||
    !getInfo ||
    !getStart
  ) {
    throw new Error("WASM exports missing (decrypt.wasm outdated?)");
  }

  const keyHex = (staticKey || DEFAULT_STATIC_KEY).slice(0, 40).toLowerCase();
  const seed = 1314 + Math.floor(9999 * Math.random());
  const collected = [];
  let running = seed;
  for (let i = 0; i < 10; i++) {
    const G = parseInt(keyHex.slice(4 * i, 4 * i + 4), 16);
    running ^= G;
    collected.push(G ^ seed);
    collected.push(running);
  }
  let xorAll = collected[19];
  for (let t = 0; t < 10; t++) xorAll ^= collected[2 * t];
  const keyArr = Array.from({ length: 10 }, (_, t) => collected[2 * t] ^ xorAll);
  const keyOff = rickRolled(seed, 40);
  let mem = wasm.H();
  for (let t = 0; t < 10; t++) {
    let h = keyArr[t].toString(16);
    h = "0".repeat(4 - h.length) + h;
    for (let n = 0; n < h.length; n++) mem[keyOff + n + 4 * t] = h.charCodeAt(n);
  }

  const diterBClean = String(diterB).replace(/\\n/g, "").replace(/\n/g, "");
  const diterBBytes = Buffer.from(diterBClean, "base64");
  reset();
  const dOff = allocDiterB(diterBBytes.length);
  mem = wasm.H();
  for (let i = 0; i < diterBBytes.length; i++) mem[dOff + i] = diterBBytes[i];
  process_(0);

  const input = new Uint8Array(encData);
  const chunks = [];
  for (let off = 0; off < input.length; off += 10240) {
    const len = Math.min(10240, input.length - off);
    const iOff = allocInput(len);
    mem = wasm.H();
    for (let i = 0; i < len; i++) mem[iOff + i] = input[off + i];
    let more = process_(1);
    while (more) {
      mem = wasm.H();
      const s = getStart();
      const e = getStart() + getInfo();
      chunks.push(Buffer.from(mem.subarray(s, e).slice(0)));
      advance();
      more = process_(0);
    }
  }
  if (!chunks.length) throw new Error("WASM produced no output");
  let result = Buffer.concat(chunks);
  if (result[0] === 0x1f && result[1] === 0x8b) {
    result = zlib.gunzipSync(result);
  }
  return result;
}

function outNameFor(binzName) {
  if (binzName === "file.binz") return "file.osgjs";
  if (binzName === "model_file.binz") return "model_file.bin";
  if (binzName === "model_file_wireframe.binz") return "model_file_wireframe.bin";
  if (binzName.endsWith(".binz")) return binzName.slice(0, -5) + ".bin";
  return binzName + ".out";
}

async function main() {
  const workDir = process.argv[2];
  let key1 = process.argv[3] || "";
  const staticKey = process.argv[4] || DEFAULT_STATIC_KEY;
  if (!workDir) {
    console.error("Usage: decrypt_worker.mjs <work_dir> <key1|@file> [static_key]");
    process.exit(2);
  }
  if (key1.startsWith("@")) {
    key1 = fs.readFileSync(key1.slice(1), "utf8");
  }
  if (!key1) {
    const kf = path.join(workDir, "key.txt");
    if (fs.existsSync(kf)) key1 = fs.readFileSync(kf, "utf8");
  }
  if (!key1) {
    console.error("key1 (diter.b) missing");
    process.exit(2);
  }

  const wasmPath = path.join(__dirname, "decrypt.wasm");
  if (!fs.existsSync(wasmPath)) {
    console.error("Missing decrypt.wasm next to decrypt_worker.mjs");
    process.exit(2);
  }
  const wasmBytes = fs.readFileSync(wasmPath);

  const binzFiles = fs
    .readdirSync(workDir)
    .filter((n) => n.toLowerCase().endsWith(".binz"))
    .sort();
  if (!binzFiles.length) {
    console.error("No .binz files in " + workDir);
    process.exit(1);
  }

  let ok = 0;
  for (const name of binzFiles) {
    const src = path.join(workDir, name);
    const dst = path.join(workDir, outNameFor(name));
    const enc = fs.readFileSync(src);
    process.stderr.write(`decrypt ${name} (${enc.length} bytes)\n`);
    const out = await decryptBinz(wasmBytes, enc, key1, staticKey);
    fs.writeFileSync(dst, out);
    process.stderr.write(`  -> ${path.basename(dst)} (${out.length} bytes)\n`);
    ok++;
  }
  console.log(JSON.stringify({ ok, files: binzFiles.length }));
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
});
