"""RTC/schedule bindings read from installed vendor adapters as data.

Serialization names are evidenced by PersistenceLayer RtcFunctionBlockAdapter,
ScheduleBlockAdapter and ReadWriteXmlHelper, and Entities RtcFunctionBlock.
No editor acceptance is claimed. RTC_EXEC has no invented native pin graph.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from .model import fail
from .rtc import RtcConfig, ScheduleConfig
from .levels import functional_level

ASSEMBLY='SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07'
PREFIX='SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.'
RTC_TYPE=PREFIX+'RtcFunctionBlock, '+ASSEMBLY
INT_TYPE=PREFIX+'FbParameterElementRangeType`1[[System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]], '+ASSEMBLY
RTC_PARAMETERS={'Day':'day','Month':'month','Year':'year','Hours':'hours','Minutes':'minutes','Seconds':'seconds'}
DAYS=('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')


def allowed_attribute(tag,name,value):
    return name=='Type' and ((tag=='IFunctionBlock' and value==RTC_TYPE) or (tag in RTC_PARAMETERS and value==INT_TYPE))


def fields(node,allowed,required=()):
    if node.attrib or (node.text or '').strip():fail('invalid RTC/schedule XML container: '+node.tag)
    found={}
    for c in node:
        if c.tag not in allowed or c.tag in found:fail('unknown or duplicate RTC/schedule field: '+c.tag)
        if (c.tail or '').strip():fail('mixed RTC/schedule XML content')
        found[c.tag]=c
    if set(required)-found.keys():fail('missing RTC/schedule fields in '+node.tag)
    return found


def scalar(node):
    if node.attrib or len(node):fail('RTC/schedule XML value must be scalar: '+node.tag)
    return node.text or ''


def number(node,low,high):
    value=scalar(node)
    if not re.fullmatch(r'0|[1-9][0-9]*',value) or len(value)>5 or not low<=int(value)<=high:
        fail('invalid RTC/schedule XML integer: '+node.tag)
    return int(value)


def read_rtc_node(node):
    if node.attrib!={'Type':RTC_TYPE}:fail('invalid native RTC block Type')
    # fields() rejects attributes on containers; the Type above is already closed.
    copy=ET.Element(node.tag);copy.extend(list(node))
    found=fields(copy,{'Address','Index','Symbol','Comment'}|RTC_PARAMETERS.keys(),{'Address','Index'}|RTC_PARAMETERS.keys())
    index=number(found['Index'],0,1)
    if scalar(found['Address'])!=f'%RTC{index}':fail('RTC XML index/address mismatch')
    values={}
    for tag,key in RTC_PARAMETERS.items():
        p=found[tag]
        if p.attrib!={'Type':INT_TYPE}:fail('invalid RTC parameter Type: '+tag)
        if len(p)!=1 or p[0].tag!='Value' or p[0].attrib or len(p[0])!=1 or p[0][0].tag!='int':fail('invalid RTC parameter shape')
        if (p.text or '').strip() or (p[0].text or '').strip():fail('mixed RTC parameter content')
        values[key]=number(p[0][0],0,32767)
    for tag in ('Symbol','Comment'):
        if tag in found:scalar(found[tag])
    return index,RtcConfig(**values)


def read_rtcs(sw):
    result={}
    for node in sw.findall('FunctionBlocks/IFunctionBlock'):
        if (node.findtext('Address','')).startswith('%RTC') or node.attrib.get('Type')==RTC_TYPE:
            i,cfg=read_rtc_node(node)
            if i in result:fail('duplicate RTC configuration')
            result[i]=cfg
    return result


def write_rtcs(program,sw):
    container=sw.find('FunctionBlocks')
    if container is None:container=ET.SubElement(sw,'FunctionBlocks')
    for old in list(container):
        if old.findtext('Address','').startswith('%RTC'):container.remove(old)
    for i,cfg in sorted(program.rtcs.items()):
        node=ET.SubElement(container,'IFunctionBlock',Type=RTC_TYPE)
        ET.SubElement(node,'Address').text=f'%RTC{i}'
        ET.SubElement(node,'Index').text=str(i)
        for tag,key in RTC_PARAMETERS.items():
            p=ET.SubElement(node,tag,Type=INT_TYPE)
            ET.SubElement(ET.SubElement(p,'Value'),'int').text=str(getattr(cfg,key))


def read_schedules(sw):
    container=sw.find('ScheduleBlocks')
    if container is None:return {}
    if container.attrib or (container.text or '').strip():fail('invalid ScheduleBlocks container')
    result={}
    seen=set()
    for node in container:
        if node.tag!='ScheduleBlock':fail('unknown ScheduleBlocks entry')
        f=fields(node,{'Address','Index','Symbol','Comment','Used','Configured','OutputBit','StartDate','EndDate',*DAYS},{'Index','StartDate','EndDate'})
        i=number(f['Index'],0,15)
        if i in seen:fail('duplicate schedule identity')
        seen.add(i)
        if 'Address' in f and scalar(f['Address'])!=f'%SCH{i}':fail('schedule XML address mismatch')
        for tag in ('Symbol','Comment'):
            if tag in f:scalar(f[tag])
        booleans={}
        for tag in (*DAYS,'Configured','Used'):
            text=scalar(f[tag]) if tag in f else 'false'
            if text not in ('true','false'):fail('invalid schedule XML boolean: '+tag)
            booleans[tag]=text=='true'
        if not booleans['Configured']:
            # Inactive editor defaults are UI/configuration only; reject any
            # contradictory active payload rather than silently executing it.
            if 'OutputBit' in f and scalar(f['OutputBit']):fail('inactive schedule with output requires explicit import policy')
            continue
        if 'OutputBit' not in f:fail('configured schedule requires output')
        dates=[]
        for tag in ('StartDate','EndDate'):
            raw=scalar(f[tag])
            # XmlConvert.ToString(DateTime,Unspecified), no timezone conversion.
            if re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:00(?:\.0+)?',raw) is None:fail('unsupported schedule date/time encoding')
            try:d=datetime.fromisoformat(raw)
            except ValueError:fail('invalid schedule calendar date')
            dates.extend((d.day,d.month,d.hour,d.minute))
        result[i]=ScheduleConfig(scalar(f['OutputBit']),*dates,sum(1<<n for n,day in enumerate(DAYS) if booleans[day]))
    return result


def write_schedules(program,sw):
    previous=sw.find('ScheduleBlocks')
    if not program.schedules and (previous is None or not len(previous)):
        return
    node=ET.Element('ScheduleBlocks')
    for i,cfg in sorted(program.schedules.items()):
        child=ET.SubElement(node,'ScheduleBlock')
        # BasePlcObjectXmlWriter emits Index; Address is optional on current versions.
        ET.SubElement(child,'Address').text=f'%SCH{i}'
        ET.SubElement(child,'Index').text=str(i)
        ET.SubElement(child,'Configured').text='true'
        ET.SubElement(child,'OutputBit').text=cfg.output
        for prefix,tag in (('start','StartDate'),('end','EndDate')):
            d=datetime(2012,getattr(cfg,prefix+'_month'),getattr(cfg,prefix+'_day'),getattr(cfg,prefix+'_hour'),getattr(cfg,prefix+'_min'))
            ET.SubElement(child,tag).text=d.isoformat(timespec='seconds')
        for n,day in enumerate(DAYS):
            if cfg.dow&(1<<n):ET.SubElement(child,day).text='true'
    if previous is None:sw.append(node)
    else:
        position=list(sw).index(previous);sw.remove(previous);sw.insert(position,node)
    old=sw.find('SchsMemoryAllocation')
    if old is not None:sw.remove(old)
    allocation=ET.SubElement(sw,'SchsMemoryAllocation')
    # Empty allocation is the observed editor default. Do not infer a family-
    # specific ForcedCount/enum binding from a different memory collection.


def profile(program,root):
    if not program.rtcs and not program.schedules:
        return
    level=functional_level(root.findtext('ManagementLevel'))
    if program.rtcs and level<(5,0):fail('RTC function blocks require functional level5.0')
    if any('%SCH' in line for rung in program.rungs for line in rung) and level<(6,0):fail('schedule member objects require functional level6.0')
    # No native pin/graph is guessed from a generic manual diagram.
    if any(line.startswith('RTC_EXEC ') for rung in program.rungs for line in rung):
        fail('compiler gap: RTC_EXEC native IL pin order/Ladder binding needs editor evidence; use documented S50/SW50..53 service API for native set/snapshot')
    capacity=root.findtext('HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/ScheduleBlocksMax')
    if program.schedules and capacity!='16':fail('target schedule capacity differs from documented TM200CE40T16')
