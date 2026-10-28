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
 * Windows BMP codec
 */

#include "precompiled.h"

#include "tex_codec.h"

#include "lib/byte_order.h"
#include "lib/code_annotation.h"
#include "lib/debug.h"
#include "lib/os_path.h"
#include "lib/status.h"
#include "lib/tex/tex.h"

#include <cstdlib>

#pragma pack(push, 1)

struct BmpHeader
{
	// BITMAPFILEHEADER
	std::uint16_t bfType;			// "BM"
	std::uint32_t bfSize;			// of file
	std::uint16_t bfReserved1;
	std::uint16_t bfReserved2;
	std::uint32_t bfOffBits;		// offset to image data

	// BITMAPINFOHEADER
	std::uint32_t biSize;
	std::int32_t biWidth;
	std::int32_t biHeight;
	std::uint16_t biPlanes;
	std::uint16_t biBitCount;
	std::uint32_t biCompression;
	std::uint32_t biSizeImage;
	// the following are unused and zeroed when writing:
	std::int32_t biXPelsPerMeter;
	std::int32_t biYPelsPerMeter;
	std::uint32_t biClrUsed;
	std::uint32_t biClrImportant;
};

#pragma pack(pop)

#define BI_RGB 0		// biCompression


Status TexCodecBmp::transform(Tex*, size_t /*transforms*/) const
{
	return INFO::TEX_CODEC_CANNOT_HANDLE;
}


bool TexCodecBmp::is_hdr(const std::uint8_t* file) const
{
	// check header signature (bfType == "BM"?).
	// we compare single bytes to be endian-safe.
	return (file[0] == 'B' && file[1] == 'M');
}


bool TexCodecBmp::is_ext(const OsPath& extension) const
{
	return extension == L".bmp";
}


size_t TexCodecBmp::hdr_size(const std::uint8_t* file) const
{
	const size_t hdr_size = sizeof(BmpHeader);
	if(file)
	{
		BmpHeader* hdr = (BmpHeader*)file;
		const std::uint32_t ofs = read_le32(&hdr->bfOffBits);
		ENSURE(ofs >= hdr_size && "bmp_hdr_size invalid");
		return ofs;
	}
	return hdr_size;
}


// requirements: uncompressed, direct color, bottom up
Status TexCodecBmp::decode(std::uint8_t* RESTRICT data, size_t /*size*/, Tex* RESTRICT t) const
{
	const BmpHeader* hdr = (const BmpHeader*)data;
	const long w       = (long)read_le32(&hdr->biWidth);
	const long h_      = (long)read_le32(&hdr->biHeight);
	const std::uint16_t bpp = read_le16(&hdr->biBitCount);
	const std::uint32_t compress = read_le32(&hdr->biCompression);

	const long h = std::labs(h_);

	size_t flags = 0;
	flags |= (h_ < 0)? TEX_TOP_DOWN : TEX_BOTTOM_UP;
	if(bpp > 16)
		flags |= TEX_BGR;
	if(bpp == 32)
		flags |= TEX_ALPHA;

	// sanity checks
	if(compress != BI_RGB)
		WARN_RETURN(ERR::TEX_COMPRESSED);

	t->m_Width  = w;
	t->m_Height = h;
	t->m_Bpp    = bpp;
	t->m_Flags  = flags;
	return INFO::OK;
}


Status TexCodecBmp::encode(Tex* RESTRICT t, DynArray* RESTRICT da) const
{
	const size_t hdr_size = sizeof(BmpHeader);	// needed for BITMAPFILEHEADER
	const size_t img_size = t->img_size();
	const size_t file_size = hdr_size + img_size;
	const std::int32_t h = (t->m_Flags & TEX_TOP_DOWN)? -static_cast<std::int32_t>(t->m_Height) :
		static_cast<std::int32_t>(t->m_Height);

	size_t transforms = t->m_Flags;
	transforms &= ~TEX_ORIENTATION;	// no flip needed - we can set top-down bit.
	transforms ^= TEX_BGR;			// BMP is native BGR.

	const BmpHeader hdr =
	{
		// BITMAPFILEHEADER
		0x4D42,				// bfType = 'B','M'
		static_cast<std::uint32_t>(file_size),		// bfSize
		0, 0,				// bfReserved1,2
		hdr_size,			// bfOffBits

		// BITMAPINFOHEADER
		40,					// biSize = sizeof(BITMAPINFOHEADER)
		static_cast<std::int32_t>(t->m_Width),
		h,
		1,					// biPlanes
		static_cast<std::uint16_t>(t->m_Bpp),
		BI_RGB,				// biCompression
		static_cast<std::uint32_t>(img_size),		// biSizeImage
		0, 0, 0, 0			// unused (bi?PelsPerMeter, biClr*)
	};
	return tex_codec_write(t, transforms, &hdr, hdr_size, da);
}
