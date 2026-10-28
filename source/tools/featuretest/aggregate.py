#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

import sys


class Date:
    def __init__(self, date):
        if date.startswith("-"):
            self.year = 0
            self.month = 0
        else:
            cols = date.split("-")
            self.year = int(cols[0])
            self.month = int(cols[1])

    def __repr__(self):
        return f"{self.year}-{self.month}"

    def __str__(self):
        return f"{self.year}-{self.month}"

    def __lt__(self, other):
        if self.year < other.year:
            return True
        return self.year == other.year and self.month < other.month

    def __gt__(self, other):
        if self.year > other.year:
            return True
        return self.year == other.year and self.month > other.month


core_features = {}
lib_features = {}
attributes = {}

with open(sys.argv[1]) as file:
    state = "discard"
    while line := file.readline():
        # discard
        if state == "discard":
            if line.startswith(("C++11 CORE", "C++14 CORE", "C++17 CORE", "C++20 CORE")):
                collection = core_features
                state = "collect"
                continue
            if line.startswith(("C++11 LIB", "C++14 LIB", "C++17 LIB CORE", "C++20 LIB")):
                collection = lib_features
                state = "collect"
                continue
            if line.startswith("ATTRIBUTES"):
                collection = attributes
                state = "collect"
                continue

        # collect
        if state == "collect":
            if line.rstrip() != "":
                cols = line.split()
                if (key := cols[0]) in collection:
                    if Date(cols[1]) < Date(collection[key][0]):
                        collection[key][0] = cols[1]
                    if Date(cols[3]) > Date(collection[key][2]):
                        collection[key][2] = cols[3]
                else:
                    collection[key] = cols[1:]
            else:
                state = "discard"


def print_features(features):
    for key, value in sorted(features.items()):
        if Date(value[0]) < Date(value[2]):
            print(value[0], "<", value[2], key)
        elif Date(value[0]) > Date(value[2]):
            print(value[0], ">", value[2], key)
        else:
            print(value[0], "=", value[2], key)


print("CORE FEATURES")
print("-------------------------------------------------------------------------------")
print_features(core_features)
print()
print()
print("LIB FEATURES")
print("-------------------------------------------------------------------------------")
print_features(lib_features)
print()
print()
print("ATTRIBUTES (MSVC reports garbage here)")
print("-------------------------------------------------------------------------------")
print_features(attributes)
