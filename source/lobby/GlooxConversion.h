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

#ifndef GLOOX_CONVERSION_H
#define GLOOX_CONVERSION_H

#include "lib/external_libraries/gloox.h"

#include <string>

/**
 * Convert a gloox presence type to an untranslated string literal to be used
 * as an identifier by the scripts.
 */
const char* GetPresenceString(const gloox::Presence::PresenceType presenceType);

/**
 * Convert a gloox role type to an untranslated string literal to be used as an
 * identifier by the scripts.
 */
const char* GetRoleString(const gloox::MUCRoomRole role);

/**
 * Convert a gloox stanza error type to string.
 * Keep in sync with Gloox documentation
 *
 * @param err Error to be converted
 * @return Converted error string
 */
std::string StanzaErrorToString(gloox::StanzaError err);

/**
 * Convert a gloox connection error enum to string
 * Keep in sync with Gloox documentation
 *
 * @param err Error to be converted
 * @return Converted error string
 */
std::string ConnectionErrorToString(gloox::ConnectionError err);

/**
 * Convert a gloox registration result enum to string
 * Keep in sync with Gloox documentation
 *
 * @param err Enum to be converted
 * @return Converted string
 */
std::string RegistrationResultToString(gloox::RegistrationResult res);

/**
 * Translates a gloox certificate error codes, i.e. gloox certificate statuses except CertOk.
 * Keep in sync with specifications.
 */
std::string CertificateErrorToString(gloox::CertStatus status);

#endif // GLOOX_CONVERSION_H
