#pragma once
// Included inside namespace plc by plc.hpp. G02 scalar additions.
// Primary source: EIO0000003289.04 pp28,53-57,67-70.
#ifdef PLC_NATIVE
inline i16 read_system_word(int n){if(n==17)return detail::bits_i16(detail::float_status);return detail::rtc_read_word(n);}
inline void write_system_word(int n,i16 value){if(n==17){detail::float_status=(unsigned short)value;return;}detail::rtc_write_word(n,value);}
inline i16 floating_status(){return read_system_word(17);}
inline void clear_floating_status(){write_system_word(17,0);}
inline i16 inc_i16(i16 a){return detail::check_i16((long long)a+1);}
inline i16 dec_i16(i16 a){return detail::check_i16((long long)a-1);}
inline i32 inc_i32(i32 a){return detail::check_i32((long long)a+1);}
inline i32 dec_i32(i32 a){return detail::check_i32((long long)a-1);}
inline void inc_word(int n){write_word(n,inc_i16(read_word(n)));}
inline void dec_word(int n){write_word(n,dec_i16(read_word(n)));}
inline void inc_dword(int n){write_dword(n,inc_i32(read_dword(n)));}
inline void dec_dword(int n){write_dword(n,dec_i32(read_dword(n)));}
namespace detail {
inline void unknown_integer(int n,int width){
    if(n<0||n+width>(word_memory_limit?word_memory_limit:8000))__builtin_trap();
    arithmetic_error=true;
    for(int i=0;i<width;++i)indeterminate_words[n+i]=65535;
}
inline void copy_numeric(int dest,int source,int width){
    if(dest<0||source<0||dest+width>8000||source+width>8000)__builtin_trap();
    // Snapshot before writing handles overlapping MD/MF identities.
    unsigned short a=words[source],at=indeterminate_words[source];
    unsigned short b=width==2?words[source+1]:0,bt=width==2?indeterminate_words[source+1]:0;
    words[dest]=a;indeterminate_words[dest]=at;
    if(width==2){words[dest+1]=b;indeterminate_words[dest+1]=bt;}
}
}
inline void div_word(int n,i16 a,i16 b){if(b==0){detail::unknown_integer(n,1);return;}write_word(n,div_i16(a,b));}
inline void rem_word(int n,i16 a,i16 b){if(b==0){detail::unknown_integer(n,1);return;}write_word(n,rem_i16(a,b));}
inline void sqrt_word(int n,i16 a){if(a<0){detail::unknown_integer(n,1);return;}write_word(n,sqrt_i16(a));}
inline void div_dword(int n,i32 a,i32 b){if(b==0){detail::unknown_integer(n,2);return;}write_dword(n,div_i32(a,b));}
inline void rem_dword(int n,i32 a,i32 b){if(b==0){detail::unknown_integer(n,2);return;}write_dword(n,rem_i32(a,b));}
inline void sqrt_dword(int n,i32 a){if(a<0){detail::unknown_integer(n,2);return;}write_dword(n,sqrt_i32(a));}
inline void copy_word(int dest,int source){detail::copy_numeric(dest,source,1);}
inline void copy_dword(int dest,int source){detail::copy_numeric(dest,source,2);}
inline void copy_real(int dest,int source){detail::copy_numeric(dest,source,2);}
#else
i16 read_system_word(int);
void write_system_word(int,i16);
i16 floating_status();
void clear_floating_status();
i16 inc_i16(i16); i16 dec_i16(i16);
i32 inc_i32(i32); i32 dec_i32(i32);
void inc_word(int); void dec_word(int);
void inc_dword(int); void dec_dword(int);
void div_word(int,i16,i16); void rem_word(int,i16,i16); void sqrt_word(int,i16);
void div_dword(int,i32,i32); void rem_dword(int,i32,i32); void sqrt_dword(int,i32);
void copy_word(int,int); void copy_dword(int,int); void copy_real(int,int);
#endif

#ifdef PLC_NATIVE
namespace detail {
inline unsigned short constant_words[512]={};
inline bool constant_defined[512]={};
inline int constant_word_limit=0;
inline void put_constant(int n,unsigned raw,int width){
    if(n<0||n+width>512||(constant_word_limit&&n+width>constant_word_limit))__builtin_trap();
    for(int i=0;i<width;++i){unsigned short v=(unsigned short)(raw>>(16*i));if(constant_defined[n+i]&&constant_words[n+i]!=v)__builtin_trap();constant_defined[n+i]=true;constant_words[n+i]=v;}
}
inline unsigned get_constant(int n,int width){if(n<0||n+width>512)__builtin_trap();return (unsigned)constant_words[n]|(width==2?(unsigned)constant_words[n+1]<<16:0U);}
inline int indexed_constant(int base,int index_word,int width){
    if(constant_word_limit<1||base<0||base+width>constant_word_limit)__builtin_trap();
    if(word_memory_limit<1||index_word<0||index_word>=word_memory_limit)__builtin_trap();
    long position=(long)base+(long)read_word(index_word);
    if(position<0||position+width>constant_word_limit){index_error=true;return base;}
    return (int)position;
}
}
struct ConstantMemory{explicit ConstantMemory(int n){if(n<1||n>512)__builtin_trap();detail::constant_word_limit=n;}};
struct ConstantWord{ConstantWord(int n,i16 v){detail::put_constant(n,(unsigned)(unsigned short)v,1);}};
struct ConstantDword{ConstantDword(int n,i32 v){detail::put_constant(n,(unsigned)v,2);}};
struct ConstantReal{ConstantReal(int n,f32 v){if(!__builtin_isfinite(v))__builtin_trap();unsigned raw;__builtin_memcpy(&raw,&v,4);detail::put_constant(n,raw,2);}};
inline i16 read_constant_word(int n){return detail::bits_i16(detail::get_constant(n,1));}
inline i32 read_constant_dword(int n){return detail::bits_i32(detail::get_constant(n,2));}
inline f32 read_constant_real(int n){unsigned raw=detail::get_constant(n,2);f32 v;__builtin_memcpy(&v,&raw,4);return v;}
inline i16 read_constant_word_indexed(int n,int index_word){return read_constant_word(detail::indexed_constant(n,index_word,1));}
inline i32 read_constant_dword_indexed(int n,int index_word){return read_constant_dword(detail::indexed_constant(n,index_word,2));}
inline f32 read_constant_real_indexed(int n,int index_word){return read_constant_real(detail::indexed_constant(n,index_word,2));}
#else
struct ConstantMemory{explicit ConstantMemory(int);};
struct ConstantWord{ConstantWord(int,i16);};
struct ConstantDword{ConstantDword(int,i32);};
struct ConstantReal{ConstantReal(int,f32);};
i16 read_constant_word(int); i32 read_constant_dword(int); f32 read_constant_real(int);
i16 read_constant_word_indexed(int,int); i32 read_constant_dword_indexed(int,int); f32 read_constant_real_indexed(int,int);
#endif
