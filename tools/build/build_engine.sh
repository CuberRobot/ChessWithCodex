#!/bin/sh
# 自己编译"单文件版"浏览器 Stockfish（wasm 以 base64 内嵌，运行时不需要任何 fetch）
#
# 为什么要自己编：现成的第三方构建（stockfish.js@10）用的是 2015 年的 emscripten，
# 它的胶水会按相对路径去找 stockfish.wasm（沙箱 CSP 拦掉且静默失败），
# 而且它开头的 moduleOverrides 会把外部注入的 wasmBinary 丢掉。
#
# 前置：brew install emscripten
# 产物：src/stockfish.js（约 671KB，单文件）→ 拷到 engines/stockfish-single.js（该目录不入库）
set -e
WORK=${WORK:-/private/tmp/sfjs}
git clone -q --depth 1 https://github.com/niklasf/stockfish.js "$WORK"
cd "$WORK/src"
python3 - <<'PY'
import pathlib
mf = pathlib.Path("Makefile"); t = mf.read_text(encoding="utf-8")
# 1) 过时参数（1.x/2.x 时代）换成现代 emscripten 认的，并加上 SINGLE_FILE=1
t = t.replace("--memory-init-file 0 ", "")
t = t.replace('-s "EXTRA_EXPORTED_RUNTIME_METHODS=[\'ccall\']"', '-s "EXPORTED_RUNTIME_METHODS=[\'ccall\']"')
t = t.replace('-s "BINARYEN_TRAP_MODE=\'allow\'" -s BINARYEN_ASYNC_COMPILATION=1 --llvm-lto 3',
              '-s SINGLE_FILE=1 -s BINARYEN_ASYNC_COMPILATION=1')
# 2) wasm 目标下不合法的 x86/macOS 参数
t = t.replace("-mdynamic-no-pic", "").replace("--llvm-lto 3", "")
mf.write_text(t, encoding="utf-8")
PY
make COMP=emscripten ARCH=wasm popcnt=no prefetch=no build -B -j4
