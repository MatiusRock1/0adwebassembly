/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D.
 *
 * 0 A.D. is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * 0 A.D. is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with 0 A.D.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "precompiled.h"

#include "JSInterface_VisualReplay.h"

#include "lib/os_path.h"
#include "lib/utf8.h"
#include "ps/CStr.h"
#include "ps/VisualReplay.h"
#include "scriptinterface/FunctionWrapper.h"

#include <string>

namespace JSI_VisualReplay
{
CStrW GetReplayDirectoryName(const CStrW& directoryName)
{
	// The string conversion is added to account for non-latin characters.
	return wstring_from_utf8(OsPath(VisualReplay::GetDirectoryPath() / directoryName).string8());
}

void RegisterScriptFunctions(const Script::Request& rq)
{
	Script::Function::Register<&VisualReplay::GetReplays>(rq, "GetReplays");
	Script::Function::Register<&VisualReplay::DeleteReplay>(rq, "DeleteReplay");
	Script::Function::Register<&VisualReplay::StartVisualReplay>(rq, "StartVisualReplay");
	Script::Function::Register<&VisualReplay::GetReplayAttributes>(rq, "GetReplayAttributes");
	Script::Function::Register<&VisualReplay::GetReplayMetadata>(rq, "GetReplayMetadata");
	Script::Function::Register<&VisualReplay::HasReplayMetadata>(rq, "HasReplayMetadata");
	Script::Function::Register<&VisualReplay::AddReplayToCache>(rq, "AddReplayToCache");
	Script::Function::Register<&GetReplayDirectoryName>(rq, "GetReplayDirectoryName");
}
}
