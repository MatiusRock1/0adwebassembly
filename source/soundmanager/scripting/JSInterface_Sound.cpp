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

#include "JSInterface_Sound.h"

#include "lib/config2.h"
#include "lib/file/vfs/vfs_path.h"
#include "scriptinterface/FunctionWrapper.h"
#include "soundmanager/ISoundManager.h"
#include "soundmanager/SoundManager.h"

#include <string>

namespace JSI_Sound
{
#if CONFIG2_AUDIO

	void StartMusic()
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetMusicEnabled(true);
	}

	void StopMusic()
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetMusicEnabled(false);
	}

	void ClearPlaylist()
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->ClearPlayListItems();
	}

	void AddPlaylistItem(const std::wstring& filename)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->AddPlayListItem(VfsPath(filename));
	}

	void StartPlaylist(bool looping)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->StartPlayList(looping );
	}

	void PlayMusic(const std::wstring& filename, bool looping)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->PlayAsMusic(filename, looping);
	}

	void PlayUISound(const std::wstring& filename, bool looping)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->PlayAsUI(filename, looping);
	}

	void PlayAmbientSound(const std::wstring& filename, bool looping)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->PlayAsAmbient(filename, looping);
	}

	bool MusicPlaying()
	{
		return true;
	}

	void SetMasterGain(float gain)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetMasterGain(gain);
	}

	void SetMusicGain(float gain)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetMusicGain(gain);
	}

	void SetAmbientGain(float gain)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetAmbientGain(gain);
	}

	void SetActionGain(float gain)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetActionGain(gain);
	}

	void SetUIGain(float gain)
	{
		if (CSoundManager* sndManager = (CSoundManager*)g_SoundManager)
			sndManager->SetUIGain(gain);
	}

#else

	bool MusicPlaying( ){ return false; }
	void PlayAmbientSound(const std::wstring& /*filename*/, bool /*looping*/ ){}
	void PlayUISound(const std::wstring& /*filename*/, bool /*looping*/ ) {}
	void PlayMusic(const std::wstring& /*filename*/, bool /*looping*/ ) {}
	void StartPlaylist(bool /*looping*/ ){}
	void AddPlaylistItem(const std::wstring& /*filename*/ ){}
	void ClearPlaylist( ){}
	void StopMusic( ){}
	void StartMusic( ){}
	void SetMasterGain(float /*gain*/){}
	void SetMusicGain(float /*gain*/){}
	void SetAmbientGain(float /*gain*/){}
	void SetActionGain(float /*gain*/){}
	void SetUIGain(float /*gain*/){}

#endif

	void RegisterScriptFunctions(const Script::Request& rq)
	{
		Script::Function::Register<&StartMusic>(rq, "StartMusic");
		Script::Function::Register<&StopMusic>(rq, "StopMusic");
		Script::Function::Register<&ClearPlaylist>(rq, "ClearPlaylist");
		Script::Function::Register<&AddPlaylistItem>(rq, "AddPlaylistItem");
		Script::Function::Register<&StartPlaylist>(rq, "StartPlaylist");
		Script::Function::Register<&PlayMusic>(rq, "PlayMusic");
		Script::Function::Register<&PlayUISound>(rq, "PlayUISound");
		Script::Function::Register<&PlayAmbientSound>(rq, "PlayAmbientSound");
		Script::Function::Register<&MusicPlaying>(rq, "MusicPlaying");
		Script::Function::Register<&SetMasterGain>(rq, "SetMasterGain");
		Script::Function::Register<&SetMusicGain>(rq, "SetMusicGain");
		Script::Function::Register<&SetAmbientGain>(rq, "SetAmbientGain");
		Script::Function::Register<&SetActionGain>(rq, "SetActionGain");
		Script::Function::Register<&SetUIGain>(rq, "SetUIGain");
	}
}
