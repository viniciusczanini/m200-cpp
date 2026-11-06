#pragma once
// Included inside namespace plc by plc.hpp. Native DR/SBR/SC objects use no MW.
// Unknown native collision/endpoint cases trap in the local runtime only.
enum class DrumOutput : int { Memory=0, Output=1 };
struct DrumCam {
    int slot; DrumOutput bank; int address; int mask;
    DrumCam(int s,DrumOutput b,int a,int m):slot(s),bank(b),address(a),mask(m){}
};
#ifdef PLC_NATIVE
namespace detail {
inline bool sbr_used[8]={},sc_used[8]={},dr_used[8]={};
// At most eight drums times sixteen configured cams; this is host bookkeeping,
// never an allocation in the PLC M/MW image.
inline int drum_cam_count=0,drum_cam_bank[128]={},drum_cam_address[128]={};
inline void claim_sequence(int i,bool* pool){if(i<0||i>=8||pool[i])__builtin_trap();pool[i]=true;}
struct SequenceDirections {
    bool r=false,up=false,down=false;
    void edges(int mask,bool reset,bool cu,bool cd,bool& ru,bool& rd,bool& active_reset){
        if(mask<1||mask>7||(!(mask&1)&&r)||(!(mask&2)&&up)||(!(mask&4)&&down))__builtin_trap();
        active_reset=(mask&1)?reset:r;
        ru=(mask&2)&&cu&&!up;rd=(mask&4)&&cd&&!down;
        if((active_reset&&(((mask&2)&&cu)||((mask&4)&&cd)||up||down))||(ru&&rd))__builtin_trap();
        if(mask&1)r=reset;if(mask&2)up=cu;if(mask&4)down=cd;
    }
};
}
class ShiftBitRegister {
    unsigned value=0;detail::SequenceDirections directions;
public:
    explicit ShiftBitRegister(int index){detail::claim_sequence(index,detail::sbr_used);}
    ShiftBitRegister(const ShiftBitRegister&)=delete;
    ShiftBitRegister& operator=(const ShiftBitRegister&)=delete;
    bool bit(int n)const{if(n<0||n>=16)__builtin_trap();return (value&(1U<<n))!=0;}
    void set_bit(int n,bool v){if(n<0||n>=16)__builtin_trap();unsigned m=1U<<n;value=v?(value|m):(value&~m);}
    void update_pins(int mask,bool r,bool cu,bool cd){
        bool up,down,reset;directions.edges(mask,r,cu,cd,up,down,reset);
        if(reset)value=0;
        else if(up){if(value&1U)__builtin_trap();value=(value<<1)&65535U;}
        else if(down){if(value&32768U)__builtin_trap();value>>=1;}
    }
    void update(bool r,bool cu,bool cd){update_pins(7,r,cu,cd);}
};
class StepCounter {
    int current=0;detail::SequenceDirections directions;
public:
    explicit StepCounter(int index){detail::claim_sequence(index,detail::sc_used);}
    StepCounter(const StepCounter&)=delete;
    StepCounter& operator=(const StepCounter&)=delete;
    bool bit(int n)const{if(n<0||n>=256)__builtin_trap();return n==current;}
    void set_bit(int n,bool v){
        if(n<0||n>=256)__builtin_trap();
        if((v&&current!=n)||(!v&&current==n))__builtin_trap();
    }
    void update_pins(int mask,bool r,bool cu,bool cd){
        bool up,down,reset;directions.edges(mask,r,cu,cd,up,down,reset);
        if(reset)current=0;
        else if(up||down){if(current<0||(up&&current==255)||(down&&current==0))__builtin_trap();current+=up?1:-1;}
    }
    void update(bool r,bool cu,bool cd){update_pins(7,r,cu,cd);}
};
class Drum {
    int count,current=0,pending=-1;bool reset_pin=false,up_pin=false;
    bool used[16]={};DrumOutput banks[16]={};int addresses[16]={},masks[16]={};
    void add(DrumCam cam){
        if(cam.slot<0||cam.slot>=16||used[cam.slot]||cam.mask<0||cam.mask>255)__builtin_trap();
        int bank=(int)cam.bank;
        if((bank!=0&&bank!=1)||cam.address<0||cam.address>=(bank==0?1024:16))__builtin_trap();
        for(int i=0;i<detail::drum_cam_count;++i)if(detail::drum_cam_bank[i]==bank&&detail::drum_cam_address[i]==cam.address)__builtin_trap();
        if(detail::drum_cam_count>=128)__builtin_trap();
        detail::drum_cam_bank[detail::drum_cam_count]=bank;detail::drum_cam_address[detail::drum_cam_count++]=cam.address;
        used[cam.slot]=true;banks[cam.slot]=cam.bank;addresses[cam.slot]=cam.address;masks[cam.slot]=cam.mask;
    }
    void apply(){
        for(int i=0;i<16;++i)if(used[i])for(int j=0;j<i;++j)
            if(used[j]&&banks[i]==banks[j]&&addresses[i]==addresses[j]&&((masks[i]>>current)&1)!=((masks[j]>>current)&1))__builtin_trap();
        for(int i=0;i<16;++i)if(used[i]){
            bool v=((masks[i]>>current)&1)!=0;
            if(banks[i]==DrumOutput::Memory)detail::memory[addresses[i]]=v;else detail::outputs[addresses[i]]=v;
        }
    }
public:
    template<typename... Cams> explicit Drum(int index,int steps,Cams... cams):count(steps){
        detail::claim_sequence(index,detail::dr_used);
        if(steps<1||steps>8||sizeof...(cams)>16)__builtin_trap();
        (add(cams),...);apply(); // construction is the local cold-start model
    }
    Drum(const Drum&)=delete;Drum& operator=(const Drum&)=delete;
    i16 step()const{return (i16)current;}
    bool full()const{return current==count-1;}
    void set_step(int value){if(value<0||value>7)__builtin_trap();pending=value;}
    void update_pins(int mask,bool r,bool u){
        if(mask<1||mask>3||(!(mask&1)&&reset_pin)||(!(mask&2)&&up_pin))__builtin_trap();
        bool reset=(mask&1)?r:reset_pin,advance=(mask&2)?u:up_pin;
        bool edge=(mask&2)&&advance&&!up_pin;
        if((reset&&advance)||(pending>=0&&(reset||edge))||(count==1&&reset))__builtin_trap();
        int next=reset?0:pending>=0?pending:edge?(current+1)%count:current;
        if(next>=count)__builtin_trap();
        if(mask&1)reset_pin=r;if(mask&2)up_pin=u;
        pending=-1;if(next!=current){current=next;apply();}
    }
    void update(bool r,bool u){update_pins(3,r,u);}
};
#else
class ShiftBitRegister {
public:
    explicit ShiftBitRegister(int);
    ShiftBitRegister(const ShiftBitRegister&)=delete;ShiftBitRegister& operator=(const ShiftBitRegister&)=delete;
    bool bit(int)const;void set_bit(int,bool);void update(bool,bool,bool);void update_pins(int,bool,bool,bool);
};
class StepCounter {
public:
    explicit StepCounter(int);
    StepCounter(const StepCounter&)=delete;StepCounter& operator=(const StepCounter&)=delete;
    bool bit(int)const;void set_bit(int,bool);void update(bool,bool,bool);void update_pins(int,bool,bool,bool);
};
class Drum {
public:
    template<typename... Cams> explicit Drum(int,int,Cams...);
    Drum(const Drum&)=delete;Drum& operator=(const Drum&)=delete;
    i16 step()const;bool full()const;void set_step(int);void update(bool,bool);void update_pins(int,bool,bool);
};
#endif
