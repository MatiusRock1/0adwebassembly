/* Copyright (C) 2022 Wildfire Games.
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
 * minimal subset of ACPI
 */

#ifndef INCLUDED_ACPI
#define INCLUDED_ACPI

#pragma pack(push, 1)

// common header for all ACPI tables
struct AcpiTable
{
	char signature[4];
	std::uint32_t size;					// table size [bytes], including header
	std::uint8_t revision;
	std::uint8_t checksum;				// to make sum of entire table == 0
	char oemId[6];
	char oemTableId[8];
	std::uint32_t oemRevision;
	char creatorId[4];
	std::uint32_t creatorRevision;
};

enum AcpiAddressSpace
{
	// (these are not generally powers-of-two - some values have been omitted.)
	ACPI_AS_MEMORY     = 0,
	ACPI_AS_IO         = 1,
	ACPI_AS_PCI_CONFIG = 2,
	ACPI_AS_SMBUS      = 4
};

// address of a struct or register
struct AcpiGenericAddress
{
	std::uint8_t addressSpaceId;
	std::uint8_t registerBitWidth;
	std::uint8_t registerBitOffset;
	std::uint8_t accessSize;
	std::uint64_t address;
};

struct FADT	// signature is FACP!
{
	AcpiTable header;
	std::uint8_t unused1[40];
	std::uint32_t pmTimerPortAddress;
	std::uint8_t unused2[16];
	std::uint16_t c2Latency;	// [us]
	std::uint16_t c3Latency;	// [us]
	std::uint8_t unused3[5];
	std::uint8_t dutyWidth;
	std::uint8_t unused4[6];
	std::uint32_t flags;
	// (ACPI4 defines additional fields after this)

	bool IsDutyCycleSupported() const
	{
		return dutyWidth != 0;
	}

	bool IsC2Supported() const
	{
		return c2Latency <= 100;	// magic value specified by ACPI
	}

	bool IsC3Supported() const
	{
		return c3Latency <= 1000;	// see above
	}
};

#pragma pack(pop)

/**
 * @param signature e.g. "RSDT"
 * @return pointer to internal storage (valid until acpi_Shutdown())
 *
 * note: the first call may be slow, e.g. if a kernel-mode driver is
 * loaded. subsequent requests will be faster since tables are cached.
 **/
const AcpiTable* acpi_GetTable(const char* signature);

/**
 * invalidates all pointers returned by acpi_GetTable.
 **/
void acpi_Shutdown();

#endif	// #ifndef INCLUDED_ACPI
