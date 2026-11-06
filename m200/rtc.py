"""RTC/calendar services (G09). Native binding status is explicit in rtc_xml.py.

Sources: EIO0000003289.04 pp158-166,207-211; EIO0000002019.06
system objects pp322-324,329-334. Elapsed clock and battery clock are independent.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import re
from .model import fail

RTC_FIELDS = ('DAY', 'MONTH', 'YEAR', 'HOURS', 'MINUTES', 'SECONDS')
SCHEDULE_FIELDS = ('STARTDAY','STARTMONTH','STARTHOUR','STARTMIN',
                   'ENDDAY','ENDMONTH','ENDHOUR','ENDMIN','DOW')
RTC_GETTERS = {f: f.lower() for f in RTC_FIELDS} | {
    'Done':'done', 'Error':'error', 'DayOfWeek':'day_of_week', 'ErrorId':'error_id'}
SCHEDULE_GETTERS = dict(zip(SCHEDULE_FIELDS, ('start_day','start_month','start_hour',
    'start_min','end_day','end_month','end_hour','end_min','dow')))
NUMERIC_PATTERN = r'(?:%RTC[01]\.(?:DAY|MONTH|YEAR|HOURS|MINUTES|SECONDS|DayOfWeek|ErrorId)|%SCH(?:[0-9]|1[0-5])\.(?:' + '|'.join(SCHEDULE_FIELDS) + r')|%SW(?:18|19|49|5[0-9]|60|114|118))'
READ_WORDS = frozenset((18,19,*range(49,61),114,118))
WRITE_WORDS = frozenset((18,19,50,51,52,53,59,60,114))
READ_BITS = frozenset((50,51,52,59))
WRITE_BITS = frozenset((50,51,59))


def integer(value, low, high, what):
    if type(value) is not int or not low <= value <= high:
        fail(f'{what} requires integer {low}..{high}')
    return value


def reference(text, writable=False):
    if text.startswith('%RTC'):
        match = re.fullmatch(r'%RTC([01])\.('+'|'.join(RTC_GETTERS)+r')', text)
        if not match: fail('invalid RTC property: '+text)
        field=match[2]
        if writable and field not in RTC_FIELDS: fail('RTC status is read-only: '+text)
        return 'rtc',int(match[1]),field
    if text.startswith('%SCH'):
        match=re.fullmatch(r'%SCH(0|[1-9][0-9]*)\.('+'|'.join(SCHEDULE_FIELDS)+r')',text)
        if not match or int(match[1])>=16: fail('invalid schedule property: '+text)
        return 'schedule',int(match[1]),match[2]
    if text.startswith('%SW'):
        match=re.fullmatch(r'%SW(0|[1-9][0-9]*)',text)
        if not match: fail('invalid RTC/system word: '+text)
        index=int(match[1])
        if index not in READ_WORDS:return None
        if writable and index not in WRITE_WORDS: fail('system word is read-only: '+text)
        return 'system',index,None
    return None


def numeric_reference(text,writable=False):
    ref=reference(text,writable)
    if ref and ref[0]=='rtc' and ref[2] in ('Done','Error'):
        fail('RTC BOOL output is not numeric: '+text)
    return ref


def cpp_read(text):
    ref=reference(text)
    if not ref:return None
    family,index,field=ref
    if family=='system':return f'plc::read_system_word({index})'
    getters=RTC_GETTERS if family=='rtc' else SCHEDULE_GETTERS
    return f'{family}_{index}.{getters[field]}()'


def cpp_write(text,value):
    ref=reference(text,True)
    if not ref:return None
    family,index,field=ref
    if family=='system':return f'plc::write_system_word({index},{value});'
    getters=RTC_GETTERS if family=='rtc' else SCHEDULE_GETTERS
    return f'{family}_{index}.set_{getters[field]}({value});'


def parse_exec(arg):
    fields=arg.split()
    if len(fields)!=3 or re.fullmatch(r'%RTC[01]',fields[0]) is None:
        fail('invalid internal RTC_EXEC operands')
    return int(fields[0][-1]),fields[1],fields[2]


@dataclass
class RtcConfig:
    day:int=12
    month:int=6
    year:int=2017
    hours:int=0
    minutes:int=0
    seconds:int=0

    def __post_init__(self):
        for value,low,high,name in ((self.day,1,31,'RTC day'),(self.month,1,12,'RTC month'),
            (self.year,2000,32767,'RTC year'),(self.hours,0,23,'RTC hours'),
            (self.minutes,0,59,'RTC minutes'),(self.seconds,0,59,'RTC seconds')):
            integer(value,low,high,name)
        # Invalid date combinations can be handled by the RTC block at runtime.


@dataclass
class ScheduleConfig:
    output:str
    start_day:int=1
    start_month:int=1
    start_hour:int=0
    start_min:int=0
    end_day:int=31
    end_month:int=12
    end_hour:int=23
    end_min:int=59
    dow:int=127

    def __post_init__(self):
        from .model import address
        if type(self.output) is not str:fail("schedule output requires an address string")
        bank,_=address(self.output,True)
        if bank not in ('M','Q0.'):fail('schedule output must be direct M/Q0 bit')
        for prefix in ('start','end'):
            integer(getattr(self,prefix+'_day'),1,31,'schedule day')
            integer(getattr(self,prefix+'_month'),1,12,'schedule month')
            integer(getattr(self,prefix+'_hour'),0,23,'schedule hour')
            integer(getattr(self,prefix+'_min'),0,59,'schedule minute')
            # 2012 is the editor's reference year, including February 29.
            try:datetime(2012,getattr(self,prefix+'_month'),getattr(self,prefix+'_day'))
            except ValueError:fail('invalid configured schedule month/day combination')
        integer(self.dow,0,127,'schedule DOW (Monday bit0..Sunday bit6)')


def configs_from_json(raw,typ,capacity):
    if not isinstance(raw,dict):fail('invalid RTC/schedule configuration map')
    result={}
    for key,value in raw.items():
        if not isinstance(key,str) or re.fullmatch(r'0|[1-9][0-9]*',key) is None or len(key)>2 or int(key)>=capacity:
            fail('invalid RTC/schedule identity')
        if not isinstance(value,dict):fail('invalid RTC/schedule configuration')
        try:result[int(key)]=typ(**value)
        except TypeError:fail('unknown or missing RTC/schedule configuration fields')
    return result


def validate_resources(program):
    for configs,typ,capacity in ((program.rtcs,RtcConfig,2),(program.schedules,ScheduleConfig,16)):
        if not isinstance(configs,dict):fail('invalid RTC/schedule configuration map')
        for key,value in configs.items():
            integer(key,0,capacity-1,'RTC/schedule identity')
            if not isinstance(value,typ):fail('invalid RTC/schedule configuration type')
            typ(**asdict(value))
    for rung in program.rungs:
        for line in rung:
            for text in re.findall(r'%(?:RTC|SCH)[0-9]+\.[A-Za-z]+',line):
                family,index,_=reference(text)
                if index not in (program.rtcs if family=='rtc' else program.schedules):
                    fail('unconfigured RTC/schedule reference: '+text)
            if line.startswith('RTC_EXEC '):
                index,_,_=parse_exec(line.split(maxsplit=1)[1])
                if index not in program.rtcs:fail('undefined RTC execution')


def bcd(value):
    return (value//1000%10<<12)|(value//100%10<<8)|(value//10%10<<4)|(value%10)


def unbcd(value):
    value &= 65535
    digits=[(value>>i)&15 for i in (12,8,4,0)]
    if max(digits)>9:raise ValueError('invalid BCD digit')
    return digits[0]*1000+digits[1]*100+digits[2]*10+digits[3]


def signed(value):
    value &=65535
    return value-65536 if value&32768 else value


def date_error(values):
    if any(type(value) is not int for value in values.values()):
        fail("RTC date/time requires integer components")
    # Error precedence follows the documented code table, not certified firmware.
    for name,low,high,code in (('year',2000,32767,1),('month',1,12,2),
        ('day',1,31,3),('hours',0,23,5),('minutes',0,59,6),('seconds',0,59,7)):
        if not low<=values[name]<=high:return code
    if values['year']>9999:
        fail('RTC host calendar beyond year9999 is a compiler-model gap; native YEAR accepts i16')
    try:datetime(values['year'],values['month'],values['day'],values['hours'],values['minutes'],values['seconds'])
    except ValueError:return 8
    return 0


class RtcClock:
    """Injectable local battery clock; invalid by default, never uses host time.

    Available describes the peripheral, valid describes initialized battery data.
    Millisecond advancement is independent of elapsed counter reset and RUN/STOP.
    """
    def __init__(self,year=2000,month=1,day=1,hours=0,minutes=0,seconds=0,*,valid=False,available=True):
        values=dict(year=year,month=month,day=day,hours=hours,minutes=minutes,seconds=seconds)
        if date_error(values):fail('invalid injected RTC date/time')
        if type(valid) is not bool or type(available) is not bool:fail('RTC health requires bools')
        self.value=datetime(year,month,day,hours,minutes,seconds)
        self.valid,self.available=valid,available
        self._last_correction=None

    def set(self,values):
        error=date_error(values)
        if error:return error
        if not self.available:return 9
        self.value=datetime(values['year'],values['month'],values['day'],values['hours'],values['minutes'],values['seconds'])
        self.valid=True
        return 0

    def fields(self):
        d=self.value
        return dict(day=d.day,month=d.month,year=d.year,hours=d.hour,minutes=d.minute,seconds=d.second)

    def advance(self,milliseconds,correction=0):
        integer(milliseconds,0,3600000,'RTC advance milliseconds')
        if not self.available:return
        old=self.value
        try:new=old+timedelta(milliseconds=milliseconds)
        except OverflowError:fail('RTC host calendar rollover beyond year9999 is not modeled')
        # M200 SW60 correction once each Sunday at00:00:30. A scan <=1h
        # crosses at most one weekly point. Negative corrections cannot retrigger.
        point=new.replace(hour=0,minute=0,second=30,microsecond=0)
        point-=timedelta(days=(point.weekday()-6)%7)
        if old<point<=new and self._last_correction!=point.date() and self.valid:
            self._last_correction=point.date()
            amount=correction&127
            if amount>30 or correction&~255:fail('invalid SW60 correction encoding')
            new+=timedelta(seconds=-amount if correction&128 else amount)
        self.value=new


class RtcState:
    def __init__(self,config):
        self.values=asdict(config)
        self.done=self.error=False
        self.day_of_week=self.error_id=0
        self.previous_write=False

    def read(self,field):
        key=RTC_GETTERS[field]
        return self.values[key] if key in self.values else getattr(self,key)

    def write(self,field,value):
        if field not in RTC_FIELDS:fail('RTC status is read-only')
        self.values[field.lower()]=integer(value,-32768,32767,'RTC member')

    def update(self,services,enable,read,write):
        edge=bool(write) and not self.previous_write
        self.previous_write=bool(write) if enable else False
        if not enable:
            self.done=self.error=False;self.day_of_week=self.error_id=0
            return
        if not read and not write:
            self.done=self.error=False
            return
        error=256 if read and write else 257 if services.gate else 0
        if not error and not services.clock.available:error=9
        if not error and read:
            if not services.clock.valid:error=9
            else:self.values=services.clock.fields()
        elif not error and write:
            if not edge:return
            error=services.clock.set(self.values)
            if not error:services.refresh()
        self.done,self.error,self.error_id=not error,bool(error),error
        if not error:self.day_of_week=services.clock.value.isoweekday()


class RtcServices:
    """Local MAST image and lifecycle, not a physical power/retention simulator.

    Schedule policy is recurring annual date window AND daily time window;
    wrap-around dates/times use OR. End minute is inclusive. Endpoint equality
    selects that date/minute. These ambiguities remain official acceptance cases.
    """
    def __init__(self,program,clock=None):
        self.clock=clock if clock is not None else RtcClock()
        if not isinstance(self.clock,RtcClock):fail('rtc must be an RtcClock')
        self.program=program
        self.controller_status=65535
        self.correction=0
        self.last_stop=[0]*4
        self.stop_cause=0
        self.absolute_ms=0
        self.reset(cold=True)

    def reset(self,*,cold):
        if type(cold) is not bool:fail('RTC lifecycle cold must be bool')
        if cold:
            self.rtcs={i:RtcState(c) for i,c in self.program.rtcs.items()}
            self.schedules={i:asdict(c) for i,c in self.program.schedules.items()}
            self.enable_mask=65535
            self.absolute_ms=0
        self.gate=False;self.adjust_enabled=False;self.adjust_mask=0
        self.write_error=False
        self.image=[0]*5
        self.refresh()

    def refresh(self):
        if self.gate:return
        d=self.clock.value
        if d.year>9999:fail('RTC BCD year representation exceeds four digits')
        self.image=[bcd(d.isoweekday()),bcd(d.second),bcd(d.hour*100+d.minute),bcd(d.month*100+d.day),bcd(d.year)]

    def bit(self,index):
        return {50:self.gate,51:not self.clock.valid or not self.clock.available,
                52:self.write_error,59:self.adjust_enabled}[index]

    def set_bit(self,index,value):
        value=bool(value)
        if index==50:
            if self.gate and not value:
                try:
                    s,hm,md,y=map(unbcd,self.image[1:])
                    values=dict(year=y,month=md//100,day=md%100,hours=hm//100,minutes=hm%100,seconds=s)
                    error=self.clock.set(values)
                except ValueError:error=8
                self.write_error=bool(error)
            self.gate=value
            self.refresh()
        elif index==51:self.clock.valid=not value
        elif index==59:
            if value and not self.adjust_enabled:self.adjust()
            self.adjust_enabled=value
        else:fail('RTC system bit is read-only')

    def read_word(self,index):
        if index==18:return (self.absolute_ms//100)%32768
        if index==19:return signed((self.absolute_ms//100)//32768)
        if 49<=index<=53:return signed(self.image[index-49])
        if 54<=index<=57:return signed(self.last_stop[index-54])
        return signed({58:self.stop_cause,59:self.adjust_mask,60:self.correction,
                       114:self.enable_mask,118:self.controller_status}[index])

    def write_word(self,index,value):
        integer(value,-32768,32767,'system word value')
        value &=65535
        if index in (18,19):
            ticks=self.absolute_ms//100
            low=ticks%32768
            high=(ticks//32768)&65535
            if index==18:
                if value>32767:fail('SW18 write exceeds documented0..32767 range')
                low=value
            else:high=value
            self.absolute_ms=(high*32768+low)*100+self.absolute_ms%100
        elif 50<=index<=53:
            if not self.gate:fail('RTC word write requires S50 staging gate')
            self.image[index-49]=value
        elif index==59:self.adjust_mask=value
        elif index==60:
            if value&~255 or (value&127)>30:fail('SW60 requires direction bit7 and magnitude0..30')
            self.correction=value
        elif index==114:self.enable_mask=value
        else:fail('RTC system word is read-only')

    def adjust(self):
        if self.gate or not self.clock.valid or not self.clock.available:return
        value=self.clock.value
        mask=self.adjust_mask
        # M200 target rule: sample SW59 on S59 rising (PROG system word table).
        # Unsupported weekday/century bits are ignored, as documented "not used".
        try:
            for offset,unit in enumerate(('seconds','minutes','hours','days'),1):
                delta=int(bool(mask&(1<<offset)))-int(bool(mask&(1<<(offset+8))))
                value+=timedelta(**{unit:delta})
            months=int(bool(mask&32))-int(bool(mask&8192))
            years=int(bool(mask&64))-int(bool(mask&16384))
            month=value.year*12+value.month-1+months+12*years
            year,month=divmod(month,12);month+=1
            if year<2000:return
            next_month=datetime(year+1,1,1) if month==12 else datetime(year,month+1,1)
            last=(next_month-timedelta(days=1)).day
            value=value.replace(year=year,month=month,day=min(value.day,last))
        except (ValueError,OverflowError):fail('RTC adjustment outside host calendar representation')
        self.clock.value=value
        self.refresh()

    def read(self,ref):
        family,index,field=ref
        if family=='system':return self.read_word(index)
        if family=='rtc':return self.rtcs[index].read(field)
        return self.schedules[index][SCHEDULE_GETTERS[field]]

    def write(self,ref,value):
        family,index,field=ref
        if family=='system':self.write_word(index,value)
        elif family=='rtc':self.rtcs[index].write(field,value)
        else:
            integer(value,-32768,32767,'schedule member')
            self.schedules[index][SCHEDULE_GETTERS[field]]=value

    def begin_scan(self,write_bit):
        self.refresh()
        outputs={c.output:False for c in self.program.schedules.values()}
        if self.clock.valid and self.clock.available:
            d=self.clock.value
            date=(d.month,d.day);minute=d.hour*60+d.minute
            for i,c in self.schedules.items():
                if not self.enable_mask&(1<<i):continue
                try:cfg=ScheduleConfig(**c)
                except ValueError:continue  # Invalid runtime member disables its window.
                start=(cfg.start_month,cfg.start_day);end=(cfg.end_month,cfg.end_day)
                sh=cfg.start_hour*60+cfg.start_min;eh=cfg.end_hour*60+cfg.end_min
                date_ok=start<=date<=end if start<=end else date>=start or date<=end
                time_ok=sh<=minute<=eh if sh<=eh else minute>=sh or minute<=eh
                active=date_ok and time_ok and bool(cfg.dow&(1<<(d.isoweekday()-1)))
                outputs[cfg.output] |= active
        for output,value in outputs.items():write_bit(output,value)

    def advance(self,dt_ms):
        self.absolute_ms+=dt_ms
        self.clock.advance(dt_ms,self.correction)

    def stop(self,cause=1):
        integer(cause,0,65535,'RTC last STOP cause')
        self.refresh()
        self.last_stop=self.image[1:].copy()
        self.stop_cause=cause
