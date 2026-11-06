"""Independent literals for natal-combined-1; no future family is required."""

from .contracts import Case, frame as F, observation as E, source_case as C


CASES = [
    C("G02_clocked_fault_partial_repair_then_later_scan_consumption",["G02"],["integer.divide","assign.scalar"],r'''
void scan(){if(plc::input(0)){plc::div_dword(4,7,0);}if(plc::input(1)){plc::write_word(4,42);}
 if(plc::input(2)){plc::write_word(5,7);}if(plc::input(3)){plc::clear_arithmetic_error();}
 if(plc::input(4)){plc::write_dword(0,plc::read_dword(4));}
 plc::output(0,plc::system(18));plc::output(1,plc::system(13));}
''',[F({0:1},17),F({},23),F({1:1,3:1},100),F({2:1,4:1},0)],{"words":[0,1],"bits":[0,1]},
      [E([0,0],[1,1]),E([0,0],[1,0]),E([0,0],[0,0]),E([42,7],[0,0])],
      "Clock positions0,17,40,140ms do not repair data or clear sticky flags. A later complete repair permits source consumption."),
    C("G02_known_overlapping_copy_snapshots_keep_flags",["G02"],["assign.scalar"],r'''
void scan(){plc::clear_arithmetic_error();plc::write_word(31,plc::shl_i16(-32768,1));
 plc::write_word(30,plc::add_i16(32767,1));plc::write_dword(0,65538);
 plc::copy_dword(1,0);plc::copy_dword(0,1);plc::copy_real(1,0);
 plc::output(0,plc::system(17));plc::output(1,plc::system(18));}
''',[F()],{"words":[0,1,2,30,31],"bits":[0,1]},[E([2,2,1,32768,0],[1,1])],
      "Snapshot each two-word source before overlapping writes; copying raw MF aliases is not arithmetic or flag reset."),
    C("G02_indeterminate_overlap_copy_then_complete_repair",["G02"],["integer.divide","assign.scalar"],r'''
void scan(){plc::clear_arithmetic_error();plc::div_dword(4,7,0);plc::copy_dword(5,4);
 plc::write_word(4,42);plc::write_word(5,7);plc::copy_dword(8,5);
 plc::write_word(6,9);plc::write_word(9,11);plc::write_dword(0,plc::read_dword(4));
 plc::write_dword(2,plc::read_dword(5));plc::write_dword(10,plc::read_dword(8));
 plc::output(0,plc::system(18));plc::clear_arithmetic_error();plc::output(1,plc::system(18));}
''',[F()],{"words":[0,1,2,3,10,11],"bits":[0,1]},[E([42,7,7,9,7,11],[1,0])],
      "No unspecified result is consumed. Overlapping copies snapshot taint, later deterministic writes repair the actual aliased cells."),
    C("G02_G06_constant_loop_guarded_fault_recovery_shared_calls",["G02","G06"],["integer.inc","integer.divide","control.subroutine"],r'''
plc::ConstantMemory constants{4};plc::ConstantWord repetitions{0,3};
void leaf(){if(!plc::input(0)){return;}plc::i16 n=0;
 while(n<plc::read_constant_word(0)){plc::inc_word(0);n=plc::inc_i16(n);}
 if(plc::input(1)){plc::div_word(1,7,0);}
 if(plc::system(18)){plc::write_word(1,23);plc::clear_arithmetic_error();}}
plc::Subroutine worker{63,leaf,"integer recovery",42};
void scan(){plc::clear_arithmetic_error();plc::write_word(0,0);plc::write_word(1,0);
 worker.call(true);worker.call(true);plc::copy_word(2,1);plc::write_word(3,30);plc::output(0,plc::system(18));}
''',[F({1:1}),F({0:1,1:1}),F({0:1})],{"words":[0,1,2,3],"bits":[0]},
      [E([0,0,0,30],[0]),E([6,23,23,30],[0]),E([6,0,0,30],[0])],
      "Two synchronous leaf calls share one image; three explicit increments each. A skipped fault has no flags, active DIV recovers to23 before copying."),
    C("G02_constants_typed_views_are_one_512_word_bank",["G02"],["assign.scalar"],r'''
plc::ConstantMemory constants{512};plc::ConstantWord low{0,-1};plc::ConstantWord high{1,0};
plc::ConstantDword pair{2,65538};plc::ConstantWord alias_low{2,2};plc::ConstantWord alias_high{3,1};
plc::ConstantReal real{4,1.0f};plc::ConstantWord last{511,-32768};
void scan(){plc::write_dword(0,plc::read_constant_dword(0));plc::write_word(2,plc::read_constant_word(2));
 plc::write_word(3,plc::read_constant_word(3));plc::write_real(8,plc::read_constant_real(4));
 plc::write_word(10,plc::read_constant_word(511));}
''',[F()],{"words":[0,1,2,3,8,9,10]},[E([65535,0,2,1,0,16256,32768])],
      "Literal low-first KW/KD and exact binary32 KF views; repeated coherent initializers are aliases, not separate banks."),
    C("G02_indexed_constants_word_and_dword_bounds_are_distinct",["G02"],["assign.scalar"],r'''
plc::WordMemory image{16};plc::ConstantMemory constants{512};
plc::ConstantWord first{0,11};plc::ConstantWord near{510,-1};plc::ConstantWord last{511,1};
void scan(){plc::write_word(0,plc::read_input_bits_i16(0,16));plc::clear_index_error();
 plc::write_word(1,plc::read_constant_word_indexed(0,0));plc::output(0,plc::system(20));
 plc::clear_index_error();plc::write_dword(2,plc::read_constant_dword_indexed(510,0));plc::output(1,plc::system(20));}
''',[F({bit:bool(raw&(1<<bit)) for bit in range(16)},0) for raw in [0,1,511,512,65535,65026]],
      {"words":[1,2,3],"bits":[0,1]},[E([11,65535,1],[0,0]),E([0,65535,1],[0,1]),E([1,65535,1],[0,1]),E([11,65535,1],[1,1]),E([11,0,65535],[1,0]),E([11,11,0],[1,0])],
      "Signed offsets0,1,511,512,-1,-510; failed access returns its base and sets S20, width2 rejects its own upper boundary."),
    C("G02_existing_float_SW17_S18_independent_recovery_control",["G02"],["float.divide","float.sqrt"],r'''
void scan(){plc::clear_arithmetic_error();plc::clear_floating_status();
 plc::write_real(0,plc::div_f32(1.0f,0.0f));plc::write_word(8,plc::floating_status());
 plc::output(0,plc::system(18));plc::clear_arithmetic_error();plc::write_word(9,plc::floating_status());
 plc::output(1,plc::system(18));plc::write_real(2,plc::sqrt_f32(-1.0f));
 plc::output(2,plc::read_real(2)!=plc::read_real(2));plc::write_word(10,plc::floating_status());
 plc::clear_floating_status();plc::write_word(11,plc::floating_status());plc::output(3,plc::system(18));}
''',[F()],{"words":[0,1,8,9,10,11],"bits":[0,1,2,3]},[E([0,32640,4,4,5,0],[1,0,1,1])],
      "Control for existing float APIs changed by G02, not deferred exotic functions. SW17 bit2/div0 and bit0/invalid; no NaN payload expectation."),
    C("G02_existing_float_copy_preserves_NaN_payload_without_ALU_fault",["G02"],["assign.scalar"],r'''
void scan(){plc::clear_arithmetic_error();plc::clear_floating_status();plc::write_word(0,4660);plc::write_word(1,32705);
 plc::copy_real(2,0);plc::output(0,plc::read_real(2)!=plc::read_real(2));plc::output(1,plc::system(18));
 plc::write_word(4,plc::floating_status());}
''',[F()],{"words":[2,3,4],"bits":[0,1]},[E([4660,32705,0],[1,0])],
      "Raw quiet NaN7FC11234 copy is exact and is not an arithmetic instruction; comparison is unordered, flag state remains unchanged."),
]


def full_constant_case():
    declarations="\n".join("plc::ConstantWord c%d{%d,%d};"%(n,n,n) for n in range(512))
    return C("G02_full_512_constant_bank_indexed_checksum",["G02"],["assign.scalar","integer.add","integer.inc"],
        "plc::WordMemory image{32};plc::ConstantMemory constants{512};\n"+declarations+r'''
void scan(){plc::write_word(31,4321);plc::i16 i=0;plc::i32 sum=0;
 while(i<512){plc::write_word(0,i);sum=plc::add_i32(sum,plc::int_to_dint(plc::read_constant_word_indexed(0,0)));i=plc::inc_i16(i);}
 plc::write_word(2,plc::read_constant_word(0));plc::write_word(3,plc::read_constant_word(511));plc::write_dword(4,sum);}
''',[F({},0)],{"words":[2,3,4,5,31]},[E([0,511,65280,1,4321])],
        "Independent sum0..511=130816=0x0001FF00;512 actual shared constants, runtime indexed loop, protected MW canary. No compiler helper calculates the expected checksum.")


TAINT_CASE = Case("G02_partial_taint_copy_and_bit_repair_guards",("G02",),("integer.divide","assign.scalar"),"G02_taint",
    "Literal determinate/indeterminate probes at alias boundaries; only complete overwritten bits become readable. Clearing S18 does not repair cells.",
    {"steps":[
      {"op":"div_dword","args":[4,7,0]}, {"op":"copy_dword","args":[5,4]}, {"op":"write_word","args":[4,42]},
      {"observe":[{"kind":"i16","index":4},{"kind":"i32","index":4},{"kind":"i32","index":5},{"kind":"s18"}]},
      {"op":"write_word","args":[5,7]}, {"op":"copy_dword","args":[8,5]},
      {"observe":[{"kind":"i32","index":4},{"kind":"i16","index":8},{"kind":"i32","index":8}]},
      {"op":"write_word","args":[6,9]}, {"observe":[{"kind":"i32","index":5},{"kind":"i32","index":8}]},
      {"op":"write_word","args":[9,11]}, {"observe":[{"kind":"i32","index":8}]},
      {"op":"clear_arithmetic_error","args":[]}, {"observe":[{"kind":"s18"}]},
      {"op":"div_word","args":[0,7,0]}, {"op":"write_word_bit","args":[0,0,True]}, {"op":"copy_word","args":[1,0]},
      {"observe":[{"kind":"bit","index":0,"bit":0},{"kind":"bit","index":0,"bit":1},{"kind":"i16","index":0},{"kind":"bit","index":1,"bit":0}]},
      *[{"op":"write_word_bit","args":[0,bit,False]} for bit in range(1,16)],
      {"observe":[{"kind":"i16","index":0},{"kind":"i16","index":1},{"kind":"s18"}]},
      {"op":"write_word","args":[1,123]}, {"observe":[{"kind":"i16","index":1}]}
    ]},
    [
      {"kind":"i16","index":4,"known":True,"value":42}, {"kind":"i32","index":4,"known":False}, {"kind":"i32","index":5,"known":False}, {"kind":"s18","known":True,"value":True},
      {"kind":"i32","index":4,"known":True,"value":458794}, {"kind":"i16","index":8,"known":True,"value":7}, {"kind":"i32","index":8,"known":False},
      {"kind":"i32","index":5,"known":True,"value":589831}, {"kind":"i32","index":8,"known":False}, {"kind":"i32","index":8,"known":True,"value":720903},
      {"kind":"s18","known":True,"value":False}, {"kind":"bit","index":0,"bit":0,"known":True,"value":True}, {"kind":"bit","index":0,"bit":1,"known":False},
      {"kind":"i16","index":0,"known":False}, {"kind":"bit","index":1,"bit":0,"known":True,"value":True},
      {"kind":"i16","index":0,"known":True,"value":1}, {"kind":"i16","index":1,"known":False}, {"kind":"s18","known":True,"value":True}, {"kind":"i16","index":1,"known":True,"value":123}
    ])


CONSTANT_BOUNDS = Case("G02_constant_bank_and_declared_allocation_boundaries",("G02",),("assign.scalar",),"G02_bounds",
    "G02 explicit ConstantMemory/WordMemory indexed ownership contract, shared512 cells, coherent versus conflicting aliases. Positive controls run in both backends.",
    {"probes":[
      {"name":"last_word","source":"plc::ConstantMemory mem{512};plc::ConstantWord a{511,-32768};void scan(){plc::write_word(0,plc::read_constant_word(511));}"},
      {"name":"last_dword","source":"plc::ConstantMemory mem{512};plc::ConstantDword a{510,-1};void scan(){plc::write_dword(0,plc::read_constant_dword(510));}"},
      {"name":"last_real","source":"plc::ConstantMemory mem{512};plc::ConstantReal a{510,1.0f};void scan(){plc::write_real(0,plc::read_constant_real(510));}"},
      {"name":"coherent_alias","source":"plc::ConstantDword a{0,65538};plc::ConstantWord b{0,2};plc::ConstantWord c{1,1};void scan(){plc::write_dword(0,plc::read_constant_dword(0));}"},
      {"name":"word512","source":"plc::ConstantWord a{512,1};void scan(){}"},
      {"name":"negative_word","source":"plc::ConstantWord a{-1,1};void scan(){}"},
      {"name":"dword511","source":"plc::ConstantDword a{511,1};void scan(){}"},
      {"name":"real511","source":"plc::ConstantReal a{511,1.0f};void scan(){}"},
      {"name":"memory0","source":"plc::ConstantMemory mem{0};void scan(){}"},
      {"name":"memory513","source":"plc::ConstantMemory mem{513};void scan(){}"},
      {"name":"conflicting_alias","source":"plc::ConstantWord a{0,1};plc::ConstantDword b{0,2};void scan(){}"},
      {"name":"initializer_beyond_declared_extent","source":"plc::ConstantMemory mem{1};plc::ConstantWord a{1,7};void scan(){}"},
      {"name":"indexed_missing_constant_memory","source":"plc::WordMemory image{8};plc::ConstantWord a{0,7};void scan(){plc::write_word(0,0);plc::write_word(1,plc::read_constant_word_indexed(0,0));}"},
      {"name":"indexed_missing_word_memory","source":"plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::write_word(0,0);plc::write_word(1,plc::read_constant_word_indexed(0,0));}"}
    ]},
    [{"name":name,"accepted":accepted} for name,accepted in [
      ("last_word",True),("last_dword",True),("last_real",True),("coherent_alias",True),
      ("word512",False),("negative_word",False),("dword511",False),("real511",False),("memory0",False),("memory513",False),
      ("conflicting_alias",False),("initializer_beyond_declared_extent",False),("indexed_missing_constant_memory",False),("indexed_missing_word_memory",False)
    ]])


FLAG_CLEAR_CASE = Case("G02_clearing_S18_alone_does_not_repair_unknown_word",("G02",),("integer.divide",),"G02_taint",
    "S18 is status, not a validity mask. Its clear leaves unknown storage unreadable until an actual deterministic write.",
    {"steps":[{"op":"div_word","args":[0,7,0]},{"op":"clear_arithmetic_error","args":[]},
              {"observe":[{"kind":"i16","index":0},{"kind":"s18"}]},{"op":"write_word","args":[0,23]},
              {"observe":[{"kind":"i16","index":0},{"kind":"s18"}]}]},
    [{"kind":"i16","index":0,"known":False},{"kind":"s18","known":True,"value":False},
     {"kind":"i16","index":0,"known":True,"value":23},{"kind":"s18","known":True,"value":False}])


OWNERSHIP_REPRO = Case("G02_indexed_constant_WordMemory_owner_required",("G02",),("assign.scalar",),"G02_bounds",
    "Isolated constructor/ownership repro for the combined-1 SDK guard divergence; run only when coordinator supplies a corrected freeze.",
    {"probes":[
      {"name":"with_both_images","source":"plc::WordMemory image{8};plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::write_word(0,0);plc::write_word(1,plc::read_constant_word_indexed(0,0));}"},
      {"name":"last_valid_index_word","source":"plc::WordMemory image{8};plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::write_word(7,0);plc::write_word(1,plc::read_constant_word_indexed(0,7));}"},
      {"name":"missing_word_image","source":"plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::write_word(0,0);plc::write_word(1,plc::read_constant_word_indexed(0,0));}"}
    ]},[{"name":"with_both_images","accepted":True},{"name":"last_valid_index_word","accepted":True},{"name":"missing_word_image","accepted":False}],
    oracle_status="prepared",notes=("Targeted repro; original SDK failure is retained in constant-bounds/results.json.",))


INDEX_TAINT_CASE = Case("G02_unknown_constant_index_requires_data_repair_not_flag_clear",("G02",),("integer.divide","assign.scalar"),"G02_bounds",
    "An unknown index must not silently select the constant base. S18 clear does not repair the index; a complete overwrite does.",
    {"probes":[
      {"name":"unknown_index_after_flag_clear","source":"plc::WordMemory image{8};plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::div_word(0,7,0);plc::clear_arithmetic_error();plc::write_word(1,plc::read_constant_word_indexed(0,0));}"},
      {"name":"repaired_index_after_flag_clear","source":"plc::WordMemory image{8};plc::ConstantMemory mem{8};plc::ConstantWord a{0,7};void scan(){plc::div_word(0,7,0);plc::clear_arithmetic_error();plc::write_word(0,0);plc::write_word(1,plc::read_constant_word_indexed(0,0));}"}
    ]},[{"name":"unknown_index_after_flag_clear","accepted":False},{"name":"repaired_index_after_flag_clear","accepted":True}])
