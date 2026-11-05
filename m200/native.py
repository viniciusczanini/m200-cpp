"""Native C++ execution is an independent reference, never a PLC certification."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .frontend import SDK
from .model import fail


def run_native(source, frames):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        fail("clang++ not found")
    source = Path(source).resolve()
    if '"' in str(source) or "\n" in str(source):
        fail("unsupported source path")
    with tempfile.TemporaryDirectory(prefix="m200-native-") as d:
        root = Path(d)
        harness = root / "harness.cpp"
        binary = root / "reference"
        harness.write_text(
            """namespace _M200NativeHarness {
extern "C" int getchar(void);
extern "C" int putchar(int);
bool read_unsigned(unsigned& value){
  int c;
  do{c=getchar();if(c<0)return false;}while(c<=32);
  value=0;
  do{if(c<'0'||c>'9')return false;value=value*10+(unsigned)(c-'0');c=getchar();}while(c>32);
  return true;
}
}
#define PLC_NATIVE
#include "%s"
int main(){
  unsigned dt; unsigned value;
  while(_M200NativeHarness::read_unsigned(dt)){
    for(int i=0;i<24;++i){if(!_M200NativeHarness::read_unsigned(value))return 2;plc::detail::inputs[i]=value!=0;}
    scan();
    for(int i=0;i<16;++i)_M200NativeHarness::putchar(plc::detail::outputs[i]?'1':'0');
    _M200NativeHarness::putchar('\\n');
    plc::detail::first_scan=false;plc::detail::now_ms+=dt;
  }
}
"""
            % str(source)
        )
        result = subprocess.run(
            [
                compiler,
                "-std=c++17",
                "-O0",
                "-I",
                str(SDK),
                str(harness),
                "-o",
                str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            fail("native reference compile failed:\n" + result.stderr)
        rows = []
        for frame in frames:
            dt = frame.get("dt_ms", 10)
            inputs = frame.get("inputs", {})
            if type(dt) is not int or not 0 <= dt <= 3600000:
                fail("invalid dt_ms")
            rows.append(
                " ".join(
                    [str(dt)]
                    + [
                        "1" if inputs.get(i, inputs.get(str(i), False)) else "0"
                        for i in range(24)
                    ]
                )
            )
        result = subprocess.run(
            [str(binary)],
            input="\n".join(rows) + "\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            fail("native reference execution failed")
        values = result.stdout.splitlines()
        if len(values) != len(frames) or any(
            len(v) != 16 or set(v) - {"0", "1"} for v in values
        ):
            fail("invalid native output")
        return [[x == "1" for x in v] for v in values]
