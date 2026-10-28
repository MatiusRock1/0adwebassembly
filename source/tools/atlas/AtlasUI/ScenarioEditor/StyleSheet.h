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

#ifndef INCLUDED_ATLAS_STYLESHEET
#define INCLUDED_ATLAS_STYLESHEET

namespace Atlas::Style
{

// Platform specific values

#if defined(__WXGTK__)
constexpr int BOTTOMBAR_DEFAULT_SIZE = 200;
constexpr int SIDEBAR_DEFAULT_SIZE = 285;
constexpr int SIDEBAR_MAINLAOYOUT_VGAP = 10;
constexpr int STATICBOX_PADDING = 5;
#elif defined(__WXOSX__) || defined(__WXMAC__)
constexpr int BOTTOMBAR_DEFAULT_SIZE = 210;
constexpr int SIDEBAR_DEFAULT_SIZE = 285;
constexpr int SIDEBAR_MAINLAOYOUT_VGAP = 5;
constexpr int STATICBOX_PADDING = 0;
#else	// __MSW__
constexpr int BOTTOMBAR_DEFAULT_SIZE = 180;
constexpr int SIDEBAR_DEFAULT_SIZE = 235;
constexpr int SIDEBAR_MAINLAOYOUT_VGAP = 5;
constexpr int STATICBOX_PADDING = 0;
#endif

} // namespace Atlas::Style

#endif // INCLUDED_ATLAS_STYLESHEET
