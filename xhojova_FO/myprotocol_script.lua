

local myprotocol = Proto("myprotocol", "My Protocol")


local f_seq = ProtoField.uint16("myprotocol.seq", "Sequence Number", base.DEC)
local f_ack = ProtoField.uint16("myprotocol.ack", "Acknowledgment Number", base.DEC)
local f_flags = ProtoField.uint8("myprotocol.flags", "Flags", base.HEX)
local f_length = ProtoField.uint16("myprotocol.length", "Length of Data", base.DEC)
local f_checksum = ProtoField.uint16("myprotocol.checksum", "Checksum", base.DEC)

myprotocol.fields = {f_seq, f_ack, f_flags, f_length, f_checksum}


local function is_data_message(flags)
    return flags == 0x00 or flags == 0x10 or flags == 0x20 or flags == 0x30
end

function myprotocol.dissector(buffer, pinfo, tree)

	pinfo.cols.protocol = "My Protocol"
	
	local subtree = tree:add(myprotocol, buffer(), "My Protocol Data")
    
	
	subtree:add(f_seq, buffer(0, 2))
    subtree:add(f_ack, buffer(2, 2))
    subtree:add(f_flags, buffer(4, 1))
    subtree:add(f_length, buffer(5, 2))
    subtree:add(f_checksum, buffer(7, 2))
	
	
	local flags_value = buffer(4, 1):uint()
	
	
	if is_data_message(flags_value) then
        -- Dátová správa (farebne odlíšená)
        subtree:add_expert_info(PI_INFO, PI_UNKNOWN, "Data message")
        pinfo.cols.info = "Data message"
        --pinfo.color = "green"
    else
        -- Režijná správa (farebne odlíšená)
        subtree:add_expert_info(PI_INFO, PI_UNKNOWN, "Control message")
        pinfo.cols.info = "Control message"
        --pinfo.color = "grey"
    
    end
end


local my_ports = DissectorTable.get("udp.port")
my_ports:add(50001, myprotocol)
my_ports:add(50002, myprotocol)
my_ports:add(60001, myprotocol)
my_ports:add(60002, myprotocol)
	
	

