"""G09 C++ AST adapters; all dynamic values retain source evaluation order."""
from .model import fail
from .numeric import Number, expect
from .lower import boolean
from .rtc import (RtcConfig, ScheduleConfig, RTC_FIELDS, RTC_GETTERS,
                  SCHEDULE_GETTERS, READ_WORDS, WRITE_WORDS, WRITE_BITS)


def declare(frontend,node,ctor,kind):
    args=ctor.get('inner',[])
    count=7 if kind=='Rtc' else 12
    if len(args)!=count:frontend.error(node,f'{kind} requires {count} explicit constructor arguments')
    values=[frontend.const(arg) for arg in args]
    if any(type(v) is not int for v in values):frontend.error(node,'RTC/schedule constructor requires integer literals')
    index=values[0]
    configs=frontend.lower.program.rtcs if kind=='Rtc' else frontend.lower.program.schedules
    capacity=2 if kind=='Rtc' else 16
    if not 0<=index<capacity or index in configs:frontend.error(node,'invalid or duplicate RTC/schedule index')
    if kind=='Rtc':cfg=RtcConfig(*values[1:])
    else:
        _,bank,output,*fields=values
        if bank not in (0,1):frontend.error(node,'schedule output bank must be0(M) or1(Q0)')
        cfg=ScheduleConfig(('%M' if bank==0 else '%Q0.')+str(output),*fields)
    configs[index]=cfg
    frontend.instances[node['id']]=(kind,index)


def member(frontend,node,kind,index,method,args,env):
    lower=frontend.lower
    getters=RTC_GETTERS if kind=='Rtc' else SCHEDULE_GETTERS
    fields={name:field for field,name in getters.items()}
    prefix=f'%RTC{index}.' if kind=='Rtc' else f'%SCH{index}.'
    if method in fields:
        if args:frontend.error(node,'RTC/schedule getter takes no arguments')
        field=fields[method]
        value=prefix+field
        return lower.copy(value if field in ('Done','Error') else Number('i16',value),'calendar_property')
    if method.startswith('set_') and method[4:] in fields:
        field=fields[method[4:]]
        if kind=='Rtc' and field not in RTC_FIELDS:frontend.error(node,'RTC status is read-only')
        if len(args)!=1:frontend.error(node,'RTC/schedule setter requires one value')
        if frontend.active:frontend.error(node,'calendar mutation is not a pure helper')
        value=expect(frontend.expr(args[0],env),'i16')
        lower.assign(Number('i16',prefix+field),value,lower.guard)
        return None
    if kind=='Rtc' and method=='update':
        if len(args)!=3:frontend.error(node,'RTC update requires enable/read/write')
        if frontend.active:frontend.error(node,'RTC update is not a pure helper')
        signals=[lower.copy(boolean(frontend.expr(arg,env)),'rtc_argument') for arg in args]
        end=None
        if lower.guard is not None:
            end=lower.new_label();lower.jump(end,lower.guard,negate=True)
        # Explicitly INTERNAL IR instruction, not a claimed vendor IL mnemonic.
        lower.rung('LD '+signals[0],f'RTC_EXEC %RTC{index} {signals[1]} {signals[2]}')
        if end is not None:lower.label(end)
        return None
    frontend.error(node,'unsupported calendar method: '+str(method))
