"""Adapt only argument-underflow handling from Mozilla D224676 to SM128.

Keep constructor/cross-realm fallbacks, the actual argc descriptor, existing
rooting and every other opcode unchanged. Padding contains undefined values.
"""


def adapt(source):
    start=source.index('  CACHEOP_CASE(CallScriptedFunction)')
    end=source.index('  CACHEOP_CASE(MetaScriptedThisShape)',start)
    before=source[start:end]
    block=before
    replacements=[(
        '''    // For now, fail any arg-underflow case.
    if (argc < callee->nargs()) {
      TRACE_PRINTF("failing: too few args\\n");
      return ICInterpretOpResult::NextIC;
    }''',
        '''    // Mozilla D224676: scripted formals need undefined padding;
    // native calls receive their actual argc without scripted padding.
    const uint32_t undefArgs = !isNative && argc < callee->nargs()
        ? callee->nargs() - argc : 0;'''),(
        '    uint32_t totalArgs = argc + extra;',
        '    uint32_t totalArgs = argc + undefArgs + extra;'),(
        '''      // Push args.
      for (uint32_t i = 0; i < totalArgs; i++) {
        PUSH(origArgs[i]);
      }''',
        '''      // Preserve the original actual-argument count and order.
      for (uint32_t i = 0; i < undefArgs; i++) {
        PUSH(StackVal(UndefinedValue()));
      }
      for (uint32_t i = 0; i < argc + extra; i++) {
        PUSH(origArgs[i]);
      }''')]
    for old,new in replacements:
        assert block.count(old)==1,('Unexpected pinned call handler',old[:70])
        block=block.replace(old,new,1)
    assert 'if (flags.isConstructing())' in block
    assert 'MakeFrameDescriptorForJitCall(FrameType::BaselineStub, argc)' in block
    return source[:start]+block+source[end:]
