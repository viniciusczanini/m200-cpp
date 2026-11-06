#pragma once
// G01 Boolean banks. This header is part of the bundled restricted SDK.
namespace plc {
#ifdef PLC_NATIVE
namespace detail {
inline bool stable_input_image=true, native_expression_blocks=false;
inline bool (*boolean_bit_hook)(const char*,bool,bool)=nullptr;
inline unsigned short (*boolean_word_hook)(const char*,bool,unsigned short)=nullptr;
inline bool boolean_system_external(int n){
    if(n<0||n>=160||!boolean_bit_hook)__builtin_trap();
    char address[6]={'%','S',0,0,0,0};int at=2;
    if(n>=100)address[at++]=char('0'+n/100);
    if(n>=10)address[at++]=char('0'+(n/10)%10);
    address[at]=char('0'+n%10);return boolean_bit_hook(address,false,false);
}
inline bool same_text(const char* a,const char* b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
inline int boolean_decimal(const char*& p){
    if(*p<'0'||*p>'9')__builtin_trap();
    const char* first=p;bool zero=*p=='0';int n=0;do{if(n>8000)__builtin_trap();n=n*10+(*p++-'0');}while(*p>='0'&&*p<='9');
    if(zero&&p-first>1)__builtin_trap();return n;
}
struct BooleanWordNode {const char* address;BooleanWordNode* next;};
inline BooleanWordNode* boolean_words=nullptr;
inline bool boolean_clear_only(int n){return n==17||n==18||n==19||n==20||n==28||n==39;}
inline bool boolean_system_writable(int n){
    switch(n){case 0:case 9:case 33:case 38:case 49:case 50:case 51:case 59:case 66:case 90:case 91:case 93:case 94:case 101:case 102:case 103:case 104:case 106:case 107:case 109:case 110:case 111:case 112:case 113:case 114:case 115:case 116:case 124:case 125:case 126:return true;default:return false;}
}
inline bool boolean_system_word_writable(int n){
    switch(n){case 0:case 1:case 11:case 17:case 18:case 19:case 33:case 34:case 35:case 36:case 37:case 38:case 49:case 50:case 51:case 52:case 53:case 59:case 60:case 76:case 77:case 78:case 79:case 101:case 102:case 103:case 104:case 105:case 106:case 111:case 112:case 113:case 114:case 121:case 122:case 123:case 148:case 206:case 224:case 225:case 226:case 227:case 228:case 229:return true;default:return false;}
}
// These identities are owned by the integrated scalar/RTC providers.
inline bool boolean_native_word(int n){return n==17||n==18||n==19||(n>=49&&n<=60)||n==114||n==118;}
inline bool boolean_native_word_writable(int n){return n==17||n==18||n==19||(n>=50&&n<=53)||n==59||n==60||n==114;}
inline unsigned short external_boolean_word(const char* address,bool write=false,unsigned short value=0){
    if(!boolean_word_hook)__builtin_trap();
    char base[16]={};unsigned i=0;
    while(address[i]&&address[i]!=':'){if(i==15)__builtin_trap();base[i]=address[i];++i;}
    return boolean_word_hook(base,write,value);
}
}
struct BooleanContext {
    BooleanContext(bool stable_inputs,bool native_edges){detail::stable_input_image=stable_inputs;detail::native_expression_blocks=native_edges;}
};
struct BooleanWord:detail::BooleanWordNode {
    explicit BooleanWord(const char* name){
        if(!name||!*name)__builtin_trap();
        for(auto p=detail::boolean_words;p;p=p->next)if(detail::same_text(name,p->address))__builtin_trap();
        address=name;next=detail::boolean_words;detail::boolean_words=this;
    }
    BooleanWord(const BooleanWord&)=delete;BooleanWord& operator=(const BooleanWord&)=delete;
};
namespace detail {
// Returns the bit value. Writes perform exactly one word RMW; the adapter
// owns system/IO side effects and can reject invalid device state/permissions.
inline bool boolean_access(const char* text,bool write,bool value,bool reset=false){
    if(text&&(text[0]=='0'||text[0]=='1')&&!text[1]){if(write)__builtin_trap();return text[0]=='1';}
    if(!text||text[0]!='%')__builtin_trap();
    const char* p=text+1;char bank=*p++;
    if((bank=='M'||bank=='S'||bank=='K')&&*p=='W'){
        ++p;int n=boolean_decimal(p);if(*p++!=':'||*p++!='X')__builtin_trap();int bit=boolean_decimal(p);if(*p||bit>=16)__builtin_trap();
#if __has_include("scalar_numeric.hpp")
        if(bank=='S'&&boolean_native_word(n)){
            if(write&&!boolean_native_word_writable(n))__builtin_trap();
            unsigned short old=(unsigned short)read_system_word(n);
            if(write)write_system_word(n,bits_i16(value?(old|(1U<<bit)):(old&~(1U<<bit))));
            return (old&(1U<<bit))!=0;
        }
#endif
        unsigned short old=0;
        if(bank=='M'){if(n>=8000)__builtin_trap();if(write){write_word_bit(n,bit,value);return value;}return read_word_bit(n,bit);}
        else if(bank=='K'){
            if(write)__builtin_trap();
#if __has_include("scalar_numeric.hpp")
            // G02 owns the only KW/KD/KF image and initializer API.
            old=(unsigned short)read_constant_word(n);
#else
            __builtin_trap(); // explicit missing G02 integration, no fake data
#endif
        }else{if(n>=234||(write&&!boolean_system_word_writable(n)))__builtin_trap();old=external_boolean_word(text);}
        if(write){unsigned short v=value?(old|(1U<<bit)):(old&~(1U<<bit));if(bank=='M')words[n]=v;else external_boolean_word(text,true,v);}
        return (old&(1U<<bit))!=0;
    }
    if((bank=='I'||bank=='Q')&&*p=='W'){
        const char* word=p+1;
        bool status=*word=='S';if(status)++word;
        // Parse both components instead of scanning past them to :X. The
        // shared decimal parser rejects aliases before a provider is called.
        int module=boolean_decimal(word);
        if(*word++!='.')__builtin_trap();
        int channel=boolean_decimal(word);
        if(*word++!=':'||*word++!='X')__builtin_trap();
        int bit=boolean_decimal(word);if(*word||bit>=16)__builtin_trap();
        if(module>14||(module==0&&(channel<100||channel>299))||(module!=0&&channel>31))__builtin_trap();
        if(write&&(bank=='I'||status))__builtin_trap();
        unsigned short old=external_boolean_word(text);
        if(write)external_boolean_word(text,true,value?(old|(1U<<bit)):(old&~(1U<<bit)));
        return (old&(1U<<bit))!=0;
    }
    int n=boolean_decimal(p);
    if(bank=='I'||bank=='Q'){
        if(n!=0||*p++!='.')__builtin_trap();n=boolean_decimal(p);if(*p||n>=(bank=='I'?24:16))__builtin_trap();
        if(bank=='I'){if(write)__builtin_trap();return inputs[n];}
        bool old=outputs[n];if(write)outputs[n]=value;return old;
    }
    if(*p)__builtin_trap();
    if(bank=='M'){if(n>=(bit_memory_limit?bit_memory_limit:1024))__builtin_trap();bool old=memory[n];if(write)memory[n]=value;return old;}
    if(bank=='S'){
        if(write){
            if(n==50||n==51||n==59){write_system(n,value);return value;}
            if(boolean_clear_only(n)){
                if(!reset||value)__builtin_trap();
                if(n==17){shift_carry=false;return false;}if(n==18){arithmetic_error=false;return false;}if(n==20){index_error=false;return false;}
            }else if(!boolean_system_writable(n))__builtin_trap();
            if(!boolean_bit_hook)__builtin_trap();return boolean_bit_hook(text,true,value);
        }
        if(n==4||n==5||n==6||n==7||n==13||n==17||n==18||n==20||n==50||n==51||n==52||n==59)return system(n);
        if(!boolean_bit_hook)__builtin_trap();return boolean_bit_hook(text,false,false);
    }
    __builtin_trap();
}
}
inline bool read_bit(const char* a){return detail::boolean_access(a,false,false);}
inline void write_bit(const char* a,bool v){detail::boolean_access(a,true,v);}
inline void set_bit(const char* a,bool enable){if(enable)detail::boolean_access(a,true,true);}
inline void reset_bit(const char* a,bool enable){if(enable)detail::boolean_access(a,true,false,true);}
class BooleanStack {
    bool values[32]={};unsigned depth=0;
public:
    BooleanStack()=default;
    BooleanStack(const BooleanStack&)=delete;BooleanStack& operator=(const BooleanStack&)=delete;
    void push(bool v){if(depth==32)__builtin_trap();values[depth++]=v;}
    bool peek()const{if(!depth)__builtin_trap();return values[depth-1];}
    bool pop(){if(!depth)__builtin_trap();return values[--depth];}
};
#else
struct BooleanContext {BooleanContext(bool,bool);};
struct BooleanWord {explicit BooleanWord(const char*);BooleanWord(const BooleanWord&)=delete;BooleanWord& operator=(const BooleanWord&)=delete;};
bool read_bit(const char*);
void write_bit(const char*,bool);
void set_bit(const char*,bool);
void reset_bit(const char*,bool);
struct BooleanStack {BooleanStack();BooleanStack(const BooleanStack&)=delete;BooleanStack& operator=(const BooleanStack&)=delete;void push(bool);bool peek()const;bool pop();};
#endif
}
