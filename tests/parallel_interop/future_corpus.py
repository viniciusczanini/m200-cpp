"""Prepared G11..G20 requests/oracles. No implementation imports or execution.

Constructor spellings come from each lane's CONTRACT.md. Oracles come from the
named manuals/standard or explicit small user algorithms, never DUT round trips.
Unbound runtime/native routes retain named pending records after integration.
"""


SPECS = []
P = "EIO0000002019.06"
G = "EIO0000003289.04"
H = "EIO0000003281.04"


def add(identity, lane, description, reference, scenario, expected, stages, oracle_pending=None):
    spec = {"identity": identity, "lane": lane, "description": description, "reference": reference, "scenario": scenario, "expected": expected, "required_stages": stages}
    if oracle_pending:
        spec["oracle_pending"] = oracle_pending
    SPECS.append(spec)


def constraint(identity, lane, description, reference, positives, negatives, fields):
    add(identity, lane, description, reference, {"mode": "cpp_constraint", "positive_sources": positives, "negative_sources": negatives, "configuration_fields": fields}, {"accepted": len(positives), "refused": len(negatives)}, ["forward", "json", "reverse"])


def native(identity, lane, source, fields, reference, template=None):
    scenario = {"mode": "native_project", "source": source, "configuration_fields": fields}
    if template:
        scenario["template"] = template
    add(identity, lane, "actual native configuration/graph binding and actual-IL reverse", reference, scenario, {"native_configuration_preserved": True}, ["forward", "project", "graph", "reverse"])


def model(identity, lane, description, reference, events, expected, api_pending):
    add(identity, lane, description, reference, {"mode": "model_scenario", "events": events, "adapter_required": api_pending}, expected, ["runtime", "configuration"])


# G11: separate dynamic property carriers from constructor enum numbering.
read = "plc::ReadVar r{0,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,20};"
constraint("G11.dynamic.property_surface", "G11", "native ID/quantity property writes and read-only status refusal", G + " pp171-187", [read + "void scan(){r.set_property(plc::CommProperty::Id,7);r.update(plc::input(0),false);plc::output(0,r.property(plc::CommProperty::Id)==7);}"], [read + "void scan(){r.set_property(plc::CommProperty::QuantityToSend,1);r.update(false,false);}", read + "void scan(){r.busy()=true;r.update(false,false);}"], ["communications"])
send = "plc::SendRecvMsg msg{0,plc::Link::Serial1,5,3,20,5,30};void scan(){msg.update(plc::input(0),plc::input(1));}"
constraint("G11.ascii.bounds", "G11", "ASCII 16 identities, byte lengths and complete word spans", G + " pp187-192", [send], [send.replace("msg{0,", "msg{16,"), send.replace(",5,3,20,5,30}", ",5,256,20,5,30}"), send.replace(",5,3,20,5,30}", ",5,3,7999,5,30}")], ["communications"])
native("G11.ascii.native_binding", "G11", send, ["communications"], G + " pp187-192", "tests/fixtures/official_tm200ce40t_modbus_bare_abort_read.smbp")
model("G11.ascii.odd_byte_and_framing", "G11", "odd-byte packing; receive capacity alone is not completion", G + " pp187-192", [{"configure": {"send_bytes": [65, 66, 67], "receive_capacity": 5, "termination": "explicit_endpoint"}}, {"receive": [120, 121]}, {"complete_endpoint_frame": True}], {"sent_bytes": [65, 66, 67], "busy_before_frame_end": True, "received_bytes": [120, 121], "quantity_received": 2, "overwritten_bytes_after_quantity": 0}, "G11 final ASCII transport hooks and quantity_received")
model("G11.exch.shared_port", "G11", "EXCH and FB contend for one physical port without implicit retry", G + " pp171,187; " + P + " pp331-332", [{"start_fb": "SL1"}, {"start_exch": 1}, {"reset_message": 1}, {"late_response": [1, 2]}], {"maximum_active_on_SL1": 1, "implicit_retries": 0, "late_memory_commits": 0}, "G11 exchange/message_reset shared engine adapter")
model("G11.dynamic.native_link_codes", "G11", "property native Link codes cannot reuse constructor enum ordinals", G + " pp171-192; G11 CONTRACT.md", [{"set_property_link": value} for value in [1, 2, 3, 4]], {"native_links": ["SL1", "SL2", "ETH1", "SL3"]}, "G11 property snapshot/readback final API")

# G12: a literal function's behavior, not the compiler's own reconstruction.
udf = 'void plus_one(){plc::set_ret_word(plc::add_i16(plc::param_word(0),1));}plc::UserFunction f{0,plus_one,"PLUSONE",10,"W","W",""};void scan(){plc::output(0,f.call_word(41)==42);}'
add("G12.udf.actual_routes", "G12", "typed UDF call preserves return and actual definition in reverse", P + " UDF/UDFB chapters; literal algorithm 41+1=42", {"mode": "cpp_trace", "source": udf, "configuration_fields": ["user_functions"], "frames": [{}, {}], "output_width": 1}, {"rows": [[True], [True]]}, ["forward", "json", "reverse", "vm", "native"])
native("G12.udf.native_binding", "G12", udf, ["user_functions"], P + " UDF configuration and native function definitions")
model("G12.udfb.instance_identity", "G12", "two instances retain separate VAR state while explicit global remains shared", P + " UDFB chapter; explicit conditional increment algorithm", [{"create_instances": [0, 1], "initial_var": 0}, {"enable": [True, False]}, {"enable": [False, True]}, {"enable": [True, False]}], {"instance_rows": [[1, 0], [1, 1], [2, 1]], "shared_increment_total": 3}, "G12 final UserBlock type strings/counts and instance-call API")
model("G12.sfc.next_scan_commit", "G12", "multi-token SFC transitions queue activation for next scan", "G12 CONTRACT.md; native SFC binding still requires final source", [{"initial_active": [0, 1]}, {"transition": {"from": [0, 1], "to": [2]}}, {"next_scan": True}], {"active_before_commit": [0, 1], "active_after_commit": [2]}, "G12 chart/run and active-set observation API")

# G13: configuration and ownership, including the valid sibling of every refusal.
digital = "plc::DigitalInput i{2,0,true};plc::DigitalOutput q{15,false,false};plc::OutputFallback f{false};void scan(){}"
constraint("G13.digital.boundaries", "G13", "last embedded pin and valid latch/filter sibling controls", P + " pp51-55; " + H + " pp65-76", [digital, "plc::DigitalInput a{23,12,false};plc::DigitalOutput b{0,true,true};void scan(){}"], [digital.replace("i{2,0,true}", "i{1,0,true}"), digital.replace("i{2,0,true}", "i{2,3,true}"), digital.replace("q{15,", "q{16,"), "plc::DigitalInput a{24,0,false};void scan(){}", "plc::DigitalInput a{2,4,false};void scan(){}"], ["digital_io"])
constraint("G13.digital.ownership", "G13", "duplicate pin/alarm and RunStop-latch collisions", P + " pp51-55", ["plc::DigitalInput a{2,0,true};plc::RunStopInput r{3};void scan(){}"], ["plc::DigitalInput a{2,0,true};plc::RunStopInput r{2};void scan(){}", "plc::DigitalInput a{2,0,false};plc::DigitalInput b{2,3,false};void scan(){}", "plc::DigitalOutput a{0,false,true};plc::DigitalOutput b{1,false,true};void scan(){}"], ["digital_io"])
native("G13.digital.native_binding", "G13", digital, ["digital_io"], P + " pp51-55")
model("G13.digital.latch_between_scans", "G13", "rising pulse >=1ms is delivered once at next scan", P + " p52; " + H + " pp65-66", [{"input": 2, "filter_ms": 0, "latch": True}, {"raw": True, "duration_us": 1000}, {"raw": False, "duration_us": 1000}, {"scan": True}, {"scan": True}], {"input_scan_rows": [True, False]}, "G13 final raw advance/pulse capture and Machine lifecycle integration")
model("G13.digital.stop_fallback", "G13", "configured ordinary fallback and maintain are distinct STOP modes", P + " pp35-37,55", [{"outputs": {"0": True, "1": False}}, {"fallback": {"0": False, "1": True}, "maintain": False}, {"STOP": True}, {"maintain": True, "RUN_outputs": {"0": True, "1": False}}, {"STOP": True}], {"ordinary_fallback": [False, True], "maintain_fallback": [True, False]}, "G13 physical-output/readback lifecycle adapter; no pulse/PTO electrical qualification")

# G14: real pin/resource conflicts, with exact constructor details deferred.
model("G14.hsc.pin_conflicts", "G14", "biphase HSC0/HSC1 exclude the overlapping single-phase channels", P + " pp61-68; " + H + " p21", [{"validate": {"HSC0": "QuadratureX1", "HSC2": "Up"}}, {"validate": {"HSC1": "QuadratureX1", "HSC3": "Up"}}, {"validate": {"HSC0": "Up", "HSC2": "Up"}}], {"accepted": [False, False, True], "conflicting_inputs": [["I0.1"], ["I0.7"]]}, "G14 FastIOConfig constructor/validate adapter")
model("G14.pulse.pin_ownership", "G14", "pulse modes/direction share exact CE40T resources", P + " pp55-61,210,223", [{"claims": ["PWM0", "PTO0"]}, {"claims": ["PTO0:CW_CCW", "PTO1"]}, {"claims": ["PWM0", "PWM1"]}], {"accepted": [False, False, True], "conflicting_outputs": [["Q0.0"], ["Q0.1"]]}, "G14 final pulse/axis typed config adapter")
model("G14.pto.single_buffer_stop", "G14", "one pending movement slot; Stop clears queued work", P + " pp232,240,248,254", [{"power_and_home": True}, {"move": {"distance": 100, "mode": "aborting"}}, {"move": {"distance": 200, "mode": "buffered"}}, {"move": {"distance": 300, "mode": "buffered"}}, {"STOP": True}], {"maximum_pending_moves": 1, "second_pending_refused": True, "pending_after_stop": 0}, "G14 logical queue observation API; physical homing/profile remain external")
model("G14.pto.home_pin_mapping", "G14", "CE40T REF/INDEX/PROBE must not use C16 mappings", P + " pp60,224,240; " + H + " pp26,69", [{"axis": 0}, {"axis": 1}], {"pins": [["I0.8", "I0.9", "I0.12"], ["I0.10", "I0.11", "I0.13"]]}, "G14 native axis config/readback adapter")

# G15: module presence and address space; analog values never fabricated.
cartridge = "plc::Cartridge c{1,plc::IoModule::TMCR2AI2};void scan(){}"
constraint("G15.hardware.slots", "G15", "cartridge slots1..2 and contiguous expansion positions1..4", P + " pp74-88; " + H + " cartridges/expansion chapters", [cartridge, "plc::Expansion e{1,plc::IoModule::TM3DI8,false};void scan(){}"], [cartridge.replace("c{1,", "c{3,"), cartridge.replace("void scan(){}", "plc::Cartridge d{1,plc::IoModule::TMCR2AI2};void scan(){}"), "plc::Expansion e{2,plc::IoModule::TM3DI8,false};void scan(){}", "plc::Expansion e{5,plc::IoModule::TM3DI8,false};void scan(){}"], ["hardware"])
native("G15.hardware.native_binding", "G15", cartridge, ["hardware"], P + " pp74-88")
model("G15.analog.explicit_injection", "G15", "separate signed I/O bank, no ADC value until explicitly observed", P + " pp74-88; G15 CONTRACT.md", [{"declare": {"slot": 1, "module": "TMCR2AI2"}}, {"read_without_observation": "%IW0.100"}, {"observe": {"%IW0.100": -32768}}, {"read": "%IW0.100"}], {"uninjected_read_refused": True, "observed_value": -32768, "mw_allocated_for_io_image": 0}, "G15 Machine.hardware public set_input/read adapter")
model("G15.hardware.embedded_absence", "G15", "CE40T has no embedded analog, distinct from missing configured cartridge", "TM200CE40T hardware manual/catalogue; docs/capabilities/HARDWARE-AUDIT.md", [{"request_embedded_analog": 0}, {"request_undeclared_cartridge_analog": "%IW0.100"}], {"classification": ["incompatible_model", "undeclared_resource"]}, "G15 final model eligibility diagnostic classification")

# G16: model limits and scanner/mapping ownership, not implicit physical clients.
ethernet = 'plc::EthernetConfig eth{0,"192.168.1.10","255.255.255.0","192.168.1.1",true,true,true};'
mapping = ethernet + "plc::ModbusMapping map{247,20,20};void scan(){}"
constraint("G16.mapping.boundaries", "G16", "mapping1..20 words and unit IDs1..247", P + " pp117-118,136,215-216", [mapping], [mapping.replace("map{247,20,20}", "map{248,20,20}"), mapping.replace("map{247,20,20}", "map{247,21,20}"), mapping.replace("map{247,20,20}", "map{247,20,0}")], ["network"])
remote = ethernet + 'plc::ModbusRemote r{15,"192.168.1.20",1,10};void scan(){}'
constraint("G16.remote.identity", "G16", "last zero-based remote identity15 is not sixteen concurrent clients", P + " pp112,118-119,338", [remote], [remote.replace("r{15,", "r{16,"), remote.replace("r{15,", "r{-1,")], ["network"])
native("G16.mapping.native_binding", "G16", mapping, ["network"], P + " pp117-118,136")
model("G16.scanner.global_ownership", "G16", "one global IOScanner, bounded devices/channels/init and explicit endpoint", P + " pp116,118-136", [{"scanner_links": ["SL1", "ETH1"]}, {"devices": 16, "channels_per_device": 10, "init_per_device": 20}, {"devices": 17}, {"channels_per_device": 11}, {"init_per_device": 21}, {"run_without_endpoint": True}], {"accepted": [False, True, False, False, False, False], "fake_endpoint_success": False}, "G16 final scanner config and endpoint adapter")
model("G16.mapping.address_spaces", "G16", "FC3 readsQWM; FC4 readsIWM; writes targetIWM, not ordinaryMW", P + " pp117-118,136,215-216", [{"mapping": {"unit": 7, "iwm": [11, 22], "qwm": [33, 44], "mw": [55, 66]}}, {"read_fc3": {"unit": 7, "first": 0, "quantity": 2}}, {"read_fc4": {"unit": 7, "first": 0, "quantity": 2}}, {"write_fc6": {"unit": 7, "first": 0, "value": 99}}, {"read_fc3": {"unit": 8, "first": 0, "quantity": 2}}], {"reads": [[33, 44], [11, 22], [55, 66]], "iwm_after_write": [99, 22], "qwm_after_write": [33, 44], "mw_after_write": [55, 66]}, "G16 local server routing adapter; no socket is needed")

# G17: exact power-loss regions, event-specific resets, request-bank distinction.
post = 'plc::PostConfiguration cfg{"ETH.IPMODE=0\\nETH.IP=192.168.1.10\\nETH.MASK=255.255.255.0\\nETH.GATEWAY=192.168.1.1\\n"};void scan(){}'
constraint("G17.post_configuration.case", "G17", "native keys are case-sensitive and wrong serial physical mode is refused", P + " pp38-40; " + H + " p77", [post], [post.replace("ETH.IP=", "eth.ip="), post.replace("ETH.IPMODE=0", "ETH.UNKNOWN=0")], ["post_configuration"])
model("G17.retention.boundaries", "G17", "power-loss auto-retention ends at MW2999/M499", P + " pp33-34", [{"write_words": {"0": 11, "2999": 22, "3000": 33, "7999": 44}, "write_bits": {"0": True, "499": True, "500": True, "1023": True}}, {"power_loss_restore_fresh_machine": True}], {"words": {"0": 11, "2999": 22, "3000": 0, "7999": 0}, "bits": {"0": True, "499": True, "500": False, "1023": False}}, "G17 RetentionImage snapshot/restore API after G18 lifecycle merge")
model("G17.retention.download_init", "G17", "download/INIT do not reuse the prior power-loss retained image", P + " pp33-34", [{"seed_retained_data": True}, {"event": "download"}, {"seed_retained_data": True}, {"event": "init"}], {"retained_words_after_each_event": [0, 0], "retained_bits_after_each_event": [False, False]}, "G17 integrated event/storage reset adapter")
model("G17.requested_nvm.bank", "G17", "requested NVM bank startsMW3000; stored length bounds restore", P + " pp34-35,325,337; G17 CONTRACT.md", [{"words": {"0": 1, "2999": 2, "3000": 3, "3001": 4, "4999": 5, "5000": 6}}, {"save_internal_count": 2}, {"overwrite_all": 99}, {"restore_internal_count": 5}], {"restored_words": {"0": 99, "2999": 99, "3000": 3, "3001": 4, "4999": 99, "5000": 99}, "SW148": 2}, "G17 S90/S93/S94/SW148 request service adapter")
model("G17.sd.run_defer", "G17", "SD insertion/request in RUN must not fabricate filesystem completion", P + " pp137-160; " + H + " pp76-79", [{"RUN": True}, {"insert_virtual_sd": {"filesystem": "FAT32", "capacity_gb": 32, "class": 4}}, {"request_memory_save": 1}, {"STOP": True}], {"completed_in_run": False, "service_allowed_after_stop": True, "native_csv_byte_format_qualified": False}, "G17 VirtualSD STOP/service boundary; byte CSV deliberately unqualified")

# G18: task priority/periods/watchdog use model time only.
add("G18.tasks.period_watchdog_bounds", "G18", "last accepted task/watchdog periods and immediately invalid neighbors", P + " pp26-28,33", {"mode": "task_constraints", "valid": [{"master_mode": "periodic", "master_period_ms": 1}, {"master_mode": "periodic", "master_period_ms": 150}, {"periodic_subroutine": 0, "periodic_period_ms": 1}, {"periodic_subroutine": 63, "periodic_period_ms": 255}, {"watchdog_ms": 10}, {"watchdog_ms": 500}], "invalid": [{"master_period_ms": 0}, {"master_period_ms": 151}, {"periodic_subroutine": 0, "periodic_period_ms": 0}, {"periodic_subroutine": 0, "periodic_period_ms": 256}, {"watchdog_ms": 9}, {"watchdog_ms": 501}]}, {"accepted": 6, "refused": 6}, ["configuration"])
add("G18.events.ownership", "G18", "event sources/priorities/SR identities are unique and bounded", P + " pp26-28; Operating Guide pp57,88-90", {"mode": "task_constraints", "valid": [{"events": [{"source": "I0.2", "subroutine": 0, "priority": 0}, {"source": "I0.5", "subroutine": 63, "priority": 7}]}], "invalid": [{"events": [{"source": "I0.1", "subroutine": 0, "priority": 0}]}, {"events": [{"source": "I0.2", "subroutine": 0, "priority": 8}]}, {"events": [{"source": "I0.2", "subroutine": 0, "priority": 0}, {"source": "I0.3", "subroutine": 1, "priority": 0}]}, {"events": [{"source": "I0.2", "subroutine": 0, "priority": 0}, {"source": "I0.3", "subroutine": 0, "priority": 1}]}]}, {"accepted": 1, "refused": 4}, ["configuration"])
model("G18.scheduler.priority", "G18", "all-ready order is event0,event7,periodic,master", P + " pp26-28", [{"all_ready": ["master", "periodic", "event7", "event0"]}, {"each_task_appends_identity_to_shared_trace": True}], {"execution_order": ["event0", "event7", "periodic", "master"]}, "G18 Machine.advance trace normalization after integration")
model("G18.scheduler.overrun_not_watchdog", "G18", "period overrun S19 and application watchdog HALTED remain distinct", P + " pp27,33,322-323", [{"master_period_ms": 1, "watchdog_ms": 10}, {"simulate_task_duration_us": 2000}, {"observe": ["S19", "state"]}, {"simulate_task_duration_us": 11000}], {"first": {"S19": True, "HALTED": False}, "second": {"HALTED": True}}, "G18 deterministic charged-instruction adapter; no host-time timing assertion")

# G19: capacities and honest absent-device behavior; no hidden plant success.
pid = "plc::Pid p{13,0,1,2,100,0,0,1,true};void scan(){p.update(false);}"
constraint("G19.pid.identity", "G19", "PID identities0..13, duplicate identity refusal", P + " pp25,309-310; " + G + " p166", [pid], [pid.replace("p{13,", "p{14,"), pid.replace("void scan()", "plc::Pid q{13,3,4,5,100,0,0,1,true};void scan()")], ["pids"])
native("G19.pid.native_binding", "G19", pid, ["pids"], P + " PID assistant configuration")
model("G19.drive.absent_endpoint", "G19", "unconfigured remote cannot report healthy Power/Done/Valid", P + " pp189-207", [{"create_axis": 15, "endpoint": None}, {"power": True}, {"read_status": True}], {"healthy": False, "power_done": False, "status_valid": False}, "G19 final explicit LocalDriveModel/absent-transport adapter")
model("G19.drive.distinct_from_pto", "G19", "remote drive blocks do not reserve embedded pulse output pins", P + " pp189-207", [{"configure_remote_drive": 0}, {"configure_PTO": 0}], {"drive_claimed_embedded_Q": [], "PTO0_still_available": True}, "G19/G14 integrated resource allocator adapter")

# G20: these assertions establish honest unknown/refusal, not native protocols.
services = ["raw_tcp", "user_udp", "opc_ua", "http_server", "mqtt", "canopen", "profinet", "ethercat", "ethernet_ip_scanner"]
add("G20.eligibility.truthful_catalogue", "G20", "nine exact services, unknown is neither absence nor authoring support", P + " p112/124-128; installed CE40T metadata; G20 CONTRACT.md", {"mode": "catalogue"}, {"count": 9, "states": {name: "metadata_claim_unbound" if name == "http_server" else "unresolved" for name in services}}, ["catalogue"])
add("G20.eligibility.closed_refusal", "G20", "native authoring/unknown names/other models refuse without I/O side effects", "G20 CONTRACT.md; primary eligibility is unresolved", {"mode": "refusal"}, {"native_services_refused": 9, "invalid_names_refused": 4, "other_model_refused": True}, ["catalogue"])
add("G20.native_protocols.unresolved", "G20", "all nine native protocol execution routes remain explicit pending", "G20 CONTRACT.md: no primary native service binding established", {"mode": "native_service_execution", "services": services}, {}, ["forward", "project", "graph", "reverse", "runtime"], "Nine G20 protocols lack target-specific primary native bindings; catalogue/refusal PASS cannot complete them")
