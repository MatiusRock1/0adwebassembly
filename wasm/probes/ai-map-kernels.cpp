/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "simulation2/helpers/AIMapKernels.h"
#include <iostream>
#include <vector>
int main(int argc, char**)
{
    std::cout.precision(17);
    std::cout << '[';
    uint32_t state = 12345;
    auto next = [&]() { state = state * 1664525u + 1013904223u; return state; };
    if (argc > 1)
    {
        for (unsigned test=0;test<10000;++test)
        {
            const int width=1+next()%48, radius=next()%((width+1)/2);
            const int x=radius+next()%(width-2*radius), y=radius+next()%(width-2*radius);
            const unsigned seed=next()%256;
            std::vector<uint8_t> bytes(width*width);
            for(size_t i=0;i<bytes.size();++i)bytes[i]=(i*37+seed)%17;
            std::vector<double> pattern{double(radius)};
            for(int i=1;i<=radius;++i)pattern.push_back(std::floor(std::sqrt(radius*radius-(i-.5)*(i-.5))+.5));
            const int result=!bytes[x+y*width] ? x+y*width : AIMapKernels::Obstruction(bytes,width,x,y,radius,pattern);
            if(test)std::cout << ',';
            std::cout << '[' << width << ',' << x << ',' << y << ',' << radius << ',' << seed << ',' << result << ']';
        }
        std::cout << "]\n";return 0;
    }
    for (unsigned test=0; test<5000; ++test)
    {
        const int width = 1+next()%32, height = 1+next()%32;
        const double cx = int(next()%96)-32 + (next()%4)*.25;
        const double cy = int(next()%96)-32 + (next()%4)*.25;
        const double distance = .25 + (next()%128)*.25;
        const double strength = (int(next()%2048)-1024)*.125;
        const double maximum = (next()%511)*.5;
        const int type = next()%3;
        std::vector<uint8_t> bytes(width*height);
        const unsigned seed = next()%256;
        for (size_t i=0;i<bytes.size();++i) bytes[i]=(i*37+seed)%256;
        AIMapKernels::AddInfluence(bytes,width,
            std::floor(std::max(0.,cx-distance)),std::floor(std::min(double(width-1),cx+distance)),
            std::floor(std::max(0.,cy-distance)),std::floor(std::min(double(height-1),cy+distance)),
            cx,cy,distance,strength ? strength : distance,maximum,type);
        if (test) std::cout << ',';
        std::cout << '[' << width << ',' << height << ',' << cx << ',' << cy << ',' << distance << ','
            << strength << ',' << maximum << ',' << type << ',' << seed << ",[";
        for (size_t i=0;i<bytes.size();++i) { if(i)std::cout << ',';std::cout << unsigned(bytes[i]); }
        std::cout << "]]";
    }
    std::cout << "]\n";
}
