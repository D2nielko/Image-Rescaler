UNAME := $(shell uname -s)
ifeq ($(UNAME),Darwin)
  LIB := build/libresize.dylib
else
  LIB := build/libresize.so
endif

CXX ?= c++
CXXFLAGS ?= -O2 -std=c++17 -fPIC -Wall -Wextra

all: $(LIB)

$(LIB): cpp/resize.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -shared -o $@ $<

clean:
	rm -rf build

.PHONY: all clean
