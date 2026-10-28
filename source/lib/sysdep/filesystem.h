/* Copyright (C) 2026 Wildfire Games.
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

/*
 * wchar_t versions of POSIX filesystem functions
 */

#ifndef INCLUDED_SYSDEP_FILESYSTEM
#define INCLUDED_SYSDEP_FILESYSTEM

#include "lib/os_path.h"
#include "lib/posix/posix_filesystem.h"	// mode_t


//
// fcntl.h
//

// transfer directly to/from user's buffer.
// treated as a request to enable aio.
#ifndef O_DIRECT	// i.e. Windows or OS X
#define O_DIRECT 0x10000000	// (value does not conflict with any current Win32 _O_* flags.)
#endif

// Win32 _wsopen_s does not open files in a manner compatible with waio.
// if its aio_read/aio_write are to be used, waio_open must (also) be called.
// calling both is possible but wasteful and unsafe, since it prevents
// file sharing restrictions, which are the only way to prevent
// exposing previous data as a side effect of waio_Preallocate.
// applications shouldn't mix aio and synchronous I/O anyway, so we
// want wopen to call either waio_open or _wsopen_s.
// since waio requires callers to respect the FILE_FLAG_NO_BUFFERING
// restrictions (sector alignment), and IRIX/BSD/Linux O_DIRECT imposes
// similar semantics, we treat that flag as a request to enable aio.
extern int wopen(const OsPath& pathname, int oflag);
extern int wopen(const OsPath& pathname, int oflag, mode_t mode);
extern int wclose(int fd);

#endif	// #ifndef INCLUDED_SYSDEP_FILESYSTEM
