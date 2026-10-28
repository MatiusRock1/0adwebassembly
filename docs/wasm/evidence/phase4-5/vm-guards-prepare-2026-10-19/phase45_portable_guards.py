"""Three pure CacheIR handlers, adapted from the pinned SM128 native compiler.

ShapeListObject in this version stores weak shapes as PrivateValue, not
PrivateGCThingValue. Its existing traceWeak compacts dead entries and updates
the initialized length. The handler only compares pointers, never dereferences
a weak shape or allocates; it cannot introduce a GC point or resurrect shapes.
"""

SDK_INPUTS = {
    'jit/CacheIRCompiler.cpp': '2ff2ee651be70d0d30537e87b9a6a46d83bc0750b16e80cc35dcaf3124b61186',
    'jit/MacroAssembler.cpp': 'efc2dbb0146cc6b28f4931f1685529d18fc6ef532d41cd01bae885145512a229',
    'jit/CacheIROps.yaml': 'ada0ee7a1ad2a9872b338293a82bfe59a05c9780e5e0cf758935f196a152261a',
    'jit/CacheIRWriter.h': 'f74ae2c4e67676f6c25aec11a6c31eba86f0eb27f229ce2b9a66e4a416a8d82c',
    'jit/BaselineCacheIRCompiler.cpp': '0e82339bd57d653e2d79c1b0ca3f013402da54e5a2c30224b2c2127fca7c8f0b',
    'vm/List.h': 'dc886349933d8d899bb3c99e1ca811b2da233ab9fa151de8de61e37b16aec8d0',
    '../public/Value.h': '6f3bc5ead73d2cea3ad66ddd6007e088e6779cfbe01cfc88b59f5131ff302d67',
}
OPS = ['LoadUndefinedResult', 'GuardMultipleShapes', 'GuardIndexIsNotDenseElement']


def adapt(source):
    handlers = {
        'LoadUndefinedResult': '''  CACHEOP_CASE(LoadUndefinedResult) {
    icregs.icResult = UndefinedValue().asRawBits();
    PREDICT_RETURN();
    DISPATCH_CACHEOP();
  }

''',
        'GuardMultipleShapes': '''  CACHEOP_CASE(GuardMultipleShapes) {
    ObjOperandId objId = icregs.cacheIRReader.objOperandId();
    uint32_t shapesOffset = icregs.cacheIRReader.stubOffset();
    JSObject* obj = reinterpret_cast<JSObject*>(icregs.icVals[objId.id()]);
    NativeObject* shapes = reinterpret_cast<NativeObject*>(
        cstub->stubInfo()->getStubRawWord(cstub, shapesOffset));
    const uint32_t length = shapes->getDenseInitializedLength();
    Shape* actualShape = obj->shape();
    bool found = false;
    // SM128 ShapeListObject stores PrivateValue weak pointers. The existing
    // GC hook compacts the list; no allocation or weak-shape dereference here.
    for (uint32_t i = 0; i < length; ++i) {
      if (shapes->getDenseElement(i).toPrivate() == actualShape) {
        found = true;
        break;
      }
    }
    if (!found) {
      return ICInterpretOpResult::NextIC;
    }
    DISPATCH_CACHEOP();
  }

''',
        'GuardIndexIsNotDenseElement': '''  CACHEOP_CASE(GuardIndexIsNotDenseElement) {
    ObjOperandId objId = icregs.cacheIRReader.objOperandId();
    Int32OperandId indexId = icregs.cacheIRReader.int32OperandId();
    NativeObject* obj =
        reinterpret_cast<NativeObject*>(icregs.icVals[objId.id()]);
    // Match the native unsigned bounds check, including negative int32s.
    const uint32_t index = uint32_t(icregs.icVals[indexId.id()]);
    if (index < obj->getDenseInitializedLength() &&
        !obj->getDenseElement(index).isMagic()) {
      return ICInterpretOpResult::NextIC;
    }
    DISPATCH_CACHEOP();
  }

''',
    }
    anchor = '  CACHEOP_CASE(GuardShape) {'
    assert source.count(anchor) == 1
    for op in OPS:
        unsupported = f'  CACHEOP_CASE_UNIMPL({op})\n'
        assert source.count(unsupported) == 1, op
        assert f'  CACHEOP_CASE({op})' not in source
        source = source.replace(unsupported, '', 1)
    return source.replace(anchor, ''.join(handlers[op] for op in OPS) + anchor, 1)
