"""Adapt only D224656's switch dispatch to the pinned SpiderMonkey 128 body.

The opcode handlers, stack/GC rules, interrupt checks and coverage stay intact.
The unused computed-goto tables are omitted so they cannot inhibit inlining;
the build suppresses unused-label diagnostics for the retained predict labels.
"""
import re


def adapt(source):
    before=source
    ic_start=source.index('  CACHEOP_CASE(ReturnFromIC) {')
    ic_end=source.index('#undef PREDICT_NEXT',ic_start)
    ic_handlers=source[ic_start:ic_end]
    js_start=source.index('    CASE(Nop) {')
    js_end=source.index('  label_default:',js_start)
    js_handlers=source[js_start:js_end]

    def replace(old,new):
        nonlocal source
        assert source.count(old)==1,('Unexpected pinned dispatch source',old[:70])
        source=source.replace(old,new,1)

    pattern=r'(#define CACHEOP_CASE\(name\)[^\n]*\n)'
    source,count=re.subn(pattern,lambda m:m[1]+'  case CacheOp::name: '+chr(92)+'\n',source)
    assert count==1
    replace('#define CACHEOP_CASE_FALLTHROUGH(name) CACHEOP_CASE(name)',
            '#define CACHEOP_CASE_FALLTHROUGH(name) [[fallthrough]]; CACHEOP_CASE(name)')
    replace('#define CACHEOP_CASE_UNIMPL(name) cacheop_##name:',
            '#define CACHEOP_CASE_UNIMPL(name) case CacheOp::name: cacheop_##name:')
    table='''  static const void* const addresses[long(CacheOp::NumOpcodes)] = {
#define OP(name, ...) &&cacheop_##name,
      CACHE_IR_OPS(OP)
#undef OP
  };'''
    replace(table,'  // Switch dispatch does not take opcode label addresses.')
    replace('  goto* addresses[long(cacheop)];','  goto phase45_cacheop_dispatch;')
    replace('  CACHEOP_CASE(ReturnFromIC) {',
            'phase45_cacheop_dispatch:\n  switch (cacheop) {\n  CACHEOP_CASE(ReturnFromIC) {')
    replace('#undef PREDICT_NEXT\n}',
            '  default:\n    MOZ_CRASH("Bad CacheIR opcode");\n  }\n#undef PREDICT_NEXT\n}')

    start=source.index('#define CASE(op) label_##op:')
    end=source.index('#define ADVANCE(delta)',start)
    source=source[:start]+'''#define CASE(op) case JSOp::op: label_##op:
#define DISPATCH() \\
    DEBUG_CHECK(); \\
    goto dispatch

'''+source[end:]
    table='''#define OPCODE_LABEL(op, ...) LABEL(op),
#define TRAILING_LABEL(v) LABEL(default),

  static const void* const addresses[EnableInterruptsPseudoOpcode + 1] = {
      FOR_EACH_OPCODE(OPCODE_LABEL)
          FOR_EACH_TRAILING_UNUSED_OPCODE(TRAILING_LABEL)};

#undef OPCODE_LABEL
#undef TRAILING_LABEL'''
    replace(table,'  // Switch dispatch does not take opcode label addresses.')
    replace('    goto* addresses[*pc];','    switch (JSOp(*pc)) {')
    replace('  label_default:\n    MOZ_CRASH("Bad opcode");\n  }',
            '  label_default:\n  default:\n    MOZ_CRASH("Bad opcode");\n    }\n  }')
    assert ic_handlers in source and js_handlers in source,'Opcode handlers changed'
    assert 'goto* addresses' not in source and '&&label_' not in source.replace('#define LABEL(op) (&&label_##op)','')
    assert before.count('InterruptCheck(cx)')==source.count('InterruptCheck(cx)')
    assert before.count('COUNT_COVERAGE_PC(')==source.count('COUNT_COVERAGE_PC(')
    return source
