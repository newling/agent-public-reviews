# Copyright Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier: MIT
"""Deterministically exercise rocisa's Windows output-drain race on a POSIX host.

This compiles the actual Windows helper against a minimal API shim. The shim
schedules the child's last write and exit between an empty pipe peek and the
process wait. It models that interleaving, not a complete Windows environment.
"""
import argparse
import pathlib
import subprocess
import tempfile

SOURCES = {
    'windows.h': r'''
#pragma once
#include <algorithm>
#include <cstring>
#include <string>
using HANDLE = int;
using DWORD = unsigned long;
using BOOL = int;
inline constexpr int FALSE=0, TRUE=1, HANDLE_FLAG_INHERIT=1, STARTF_USESTDHANDLES=1;
inline constexpr int STD_OUTPUT_HANDLE=1, STD_ERROR_HANDLE=2, WAIT_OBJECT_0=0, ERROR_BROKEN_PIPE=109;
inline constexpr DWORD INFINITE=0xffffffff;
struct PROCESS_INFORMATION { HANDLE hProcess, hThread; };
struct SECURITY_ATTRIBUTES { int nLength; BOOL bInheritHandle; void* lpSecurityDescriptor; };
struct STARTUPINFOA { int cb; HANDLE hStdInput, hStdOutput, hStdError; int dwFlags; };
inline void ZeroMemory(void* p, size_t n) { std::memset(p,0,n); }
inline BOOL CloseHandle(HANDLE) { return TRUE; }
inline BOOL CreatePipe(HANDLE* r,HANDLE* w,void*,int) { *r=1; *w=2; return TRUE; }
inline BOOL SetHandleInformation(HANDLE,int,int) { return TRUE; }
inline HANDLE GetStdHandle(int h) { return h; }
inline std::string remaining;
inline bool childRunning;
inline BOOL CreateProcessA(void*,char*,void*,void*,BOOL,int,void*,void*,void*,PROCESS_INFORMATION* p) {
 p->hProcess=3; p->hThread=4; childRunning=true;
 remaining="<stdin>:1:1: error: first rejection\n";
 return TRUE;
}
inline BOOL WriteFile(HANDLE,const void*,DWORD n,DWORD* written,void*) { *written=n; return TRUE; }
inline BOOL PeekNamedPipe(HANDLE,void*,int,void*,DWORD* available,void*) { *available=remaining.size(); return TRUE; }
inline DWORD WaitForSingleObject(HANDLE,DWORD timeout) {
 // The child writes its last diagnostic after PeekNamedPipe sees no data,
 // and exits before this wait checks its process handle.
 if(timeout==0 && childRunning) { remaining="<stdin>:2:1: error: last rejection\n"; childRunning=false; }
 return WAIT_OBJECT_0;
}
inline void Sleep(int) {}
inline DWORD GetLastError() { return 0; }
inline BOOL GetExitCodeProcess(HANDLE,DWORD* code) { *code=1; return TRUE; }
inline BOOL ReadFile(HANDLE,void* buf,DWORD n,DWORD* read,void*) {
 *read=std::min<size_t>(n,remaining.size()); std::memcpy(buf,remaining.data(),*read); remaining.erase(0,*read); return TRUE;
}

inline constexpr DWORD WAIT_FAILED=0xffffffff;
''',
    'dbghelp.h': r'''
#pragma once
inline constexpr int UNDNAME_COMPLETE=0;
inline bool UnDecorateSymbolName(const char*,char*,int,int) { return false; }
''',
    'probe.cpp': r'''
#include "helper.hpp"
#include <iostream>
int main() {
 char assembler[] = "assembler";
 std::vector<char*> command = {assembler, nullptr};
 auto [status, output] = run(command, "first\nlast\n", false, true);
 bool first = output.find(":1:1: error:") != std::string::npos;
 bool last = output.find(":2:1: error:") != std::string::npos;
 std::cout << "first diagnostic captured=" << first << "\n";
 std::cout << "last diagnostic captured=" << last << "\n";
 return status == 1 && first && last ? 0 : 1;
}
'''
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=pathlib.Path)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    native = args.source_root.resolve() / "projects/hipblaslt/tensilelite/rocisa/rocisa"
    with tempfile.TemporaryDirectory(prefix="rocisa-output-drain-") as tmp:
        work = pathlib.Path(tmp)
        for name, source in SOURCES.items():
            (work / name).write_text(source)
        binary = work / "probe"
        subprocess.run(
            [args.cxx, "-std=c++20", "-D_WIN32", "-Wno-unknown-pragmas",
             "-Wno-null-conversion", "-I", str(work), "-I", str(native / "include"),
             str(work / "probe.cpp"), str(native / "src/helper.cpp"), "-o", str(binary)],
            check=True,
        )
        return subprocess.run([str(binary)], timeout=10).returncode


if __name__ == "__main__":
    raise SystemExit(main())
