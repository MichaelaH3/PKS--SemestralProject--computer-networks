import os
import socket
import threading
import struct
import time


'''Client1_IP = "10.10.35.46"
Client1_receive_PORT = 50001
Client1_send_PORT = 50002

Client2_IP = "10.10.35.46"
Client2_receive_PORT = 60001
Client2_send_PORT = 60002'''



seq_num = 0


connection_active = True
connection = False
probably_connection_lost = False
command = False

init_T = False
accept_T = False

heartbeat_count = 0
heartbeat_active = True

message_correct = False
#fragment_correct = False

sended_fragments = False
first_seq = 0



def create_my_header(seq_n, ack_n, flags, length_of_data, checksum):
    header = struct.pack('!HHBHH', seq_n, ack_n, flags, length_of_data, checksum)
    return header


def initialize_sockets():

    sock_receive = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock_receive.bind((Client1_IP, Client1_receive_PORT))
    sock_send.bind((Client1_IP, Client1_send_PORT))

    return sock_receive, sock_send


def calculate_checksum(data):

    if isinstance(data, str):
        data = data.encode('utf-8')

    checksum = 0
    for i, byte in enumerate(data):
        checksum += byte * (2 ** i)

    return checksum & 0xFFFF


def receive_message():
    global connection, init_T, connection_active, heartbeat_count, message_correct, heartbeat_active, sended_fragments

    expected_seq_num = 0
    received_fragments = []
    #fragment_position = 0
    size_of_file = 0
    size_of_message = 0


    while connection_active:
        try:
            data, client = sock_receive.recvfrom(1500)
            header = data[:9]
            message = data[9:]


            if not message:
                rec_seq_n, rec_ack_n, rec_flags, rec_length_of_data, rec_checksum = struct.unpack('!HHBHH', header)

                if rec_flags == 0b00001000:  # heartbeat flag
                    #print("Received Heartbeat")
                    heartbeat_active = True
                    heartbeat_count = 0

                if rec_flags == 0b00000001:  # prijatie syn (handshake)
                    ack_syn_header = create_my_header(0, 0, 0b00000011, 0, 0)
                    #print("Syn sa prijal")
                    handshake(ack_syn_header)

                elif rec_flags == 0b00001100:  #pozastavenie hearbeatu
                    heartbeat_active = False

                elif rec_flags == 0b00000011: #prijatie syn-ack (handshake)
                    ack_header = create_my_header(0, 0, 0b00000010, 0, 0)
                    #print("syn ack sa prijal")
                    handshake(ack_header)

                elif rec_flags == 0b00000010 and rec_ack_n == 0: #dokoncenie hanshaku - prijatie ack
                    #print("ack sa prijal")
                    print("\nHandshake was successfull(press Enter)\n")
                    connection = True
                    receive_thread = threading.Thread(target=receive_message)
                    receive_thread.start()

                    heartbeat_thread = threading.Thread(target=handle_heartbeat())
                    heartbeat_thread.start()


                elif rec_flags == 0b01000000: #prijatie fin (terminate)
                    #print("fin receive")
                    term_ack_header = create_my_header(0, 0, 0b01000010, 0, 0)
                    terminate(term_ack_header)

                elif rec_flags == 0b01000010: #prijatie ack-fin (terminate) + dokoncenie terminatu
                    init_T = True
                    #print("ackfin receive")
                    if init_T and accept_T:
                        print("\nTermination handshake completed. Closing connection. (press Enter)")
                        connection_active = False
                        close_sockets()
                        break

                elif rec_flags == 0b00000010 and rec_ack_n != 0:    #ack pri message
                    #print("prislo pos prtvr o prijati", rec_ack_n)
                    message_correct = True
                elif rec_flags == 0b00000100 and rec_ack_n != 0:
                    #print("prislo neg prtvr o prijati", rec_ack_n)
                    message_correct = False
                elif rec_flags == 0b00010010:                       #ack pri file
                    #print("prislo pos ack o fragmente c", rec_ack_n)
                    sended_fragments[rec_ack_n-first_seq] = 1
                elif rec_flags == 0b00010100:
                    #print("prislo neg ack o fragmente c", rec_ack_n)
                    sended_fragments[rec_ack_n - first_seq] = 0

            else:
                rec_seq_n, rec_ack_n, rec_flags, rec_length_of_data, rec_checksum = struct.unpack('!HHBHH', header)

                if rec_flags == 0b00100000:  #file no fragment
                    checksum = calculate_checksum(message)#.decode('utf-8'))
                    if checksum == rec_checksum:
                        ack = rec_seq_n
                        positive_ack_header = create_my_header(0, ack, 0b00000010, 0, 0)
                        sock_send.sendto(positive_ack_header, (Client2_IP, Client2_receive_PORT))

                        with open(path+"\\" + filename, 'wb') as f:
                            f.write(message)
                        print("\nThe file", filename, "with a size of", size_of_file, "was successfully received and saved (absolute path:", path, ")")
                        size_of_file = 0
                        print("\n---------------File Receive End---------------")
                    else:
                        print("\nThe file was wrong, sending a negative acknowledgment to request the file again")
                        ack = rec_seq_n
                        negative_ack_header = create_my_header(0, ack, 0b00000100, 0, 0)
                        sock_send.sendto(negative_ack_header, (Client2_IP, Client2_receive_PORT))

                elif rec_flags == 0b00110000: #fragment of file

                    checksum = calculate_checksum(message)#.decode('utf-8'))
                    #print(checksum, rec_checksum)
                    if checksum == rec_checksum:
                        ack = rec_seq_n
                        positive_ack_header = create_my_header(0, ack, 0b00010010, 0, 0)
                        sock_send.sendto(positive_ack_header, (Client2_IP, Client2_receive_PORT))
                        print("Fragment with sequence number", rec_seq_n, "was received successfully.")

                        received_fragments[rec_seq_n - expected_seq_num] = message
                        #fragment_position+=1

                        if None not in received_fragments:

                            with (open(path+"\\" + filename, 'wb') as f):
                                for fragment in received_fragments:
                                    f.write(fragment)
                            end_time = time.time()
                            print("\nThe file", filename, "with a size of", size_of_file, "bytes was successfully received and saved (absolute path:", path, ")")
                            print("Transmission duration in seconds:", round(end_time - start_time, 4))

                            print("\n---------------File Receive End---------------")

                            #fragment_position = 0
                            #expected_seq_num = 0
                            received_fragments = []
                            size_of_file = 0
                    else:
                        print("Fragment with sequence number", rec_seq_n, "was received with an error during transmission \n Sending NACK to request the file again")
                        ack = rec_seq_n
                        negative_ack_header = create_my_header(0, ack, 0b00010100, 0, 0)
                        sock_send.sendto(negative_ack_header, (Client2_IP, Client2_receive_PORT))

                elif rec_flags == 0b00010000: #fragment of message
                    checksum = calculate_checksum(message)  # .decode('utf-8'))
                    # print(checksum, rec_checksum)
                    if checksum == rec_checksum:
                        ack = rec_seq_n
                        positive_ack_header = create_my_header(0, ack, 0b00010010, 0, 0)
                        sock_send.sendto(positive_ack_header, (Client2_IP, Client2_receive_PORT))
                        print("Fragment with sequence number", rec_seq_n, "was received successfully.")

                        received_fragments[rec_seq_n - expected_seq_num] = message
                        #fragment_position += 1

                        if None not in received_fragments:
                            full_message = ""
                            for fragment in received_fragments:
                                full_message += fragment.decode("utf-8")

                            end_time = time.time()

                            print("\nMessage: ")
                            print(full_message)

                            print("\nThe message with a size of", size_of_message, "was successfully received")
                            print("Transmission duration in seconds:", round(end_time - start_time, 4))

                            print("\n---------------Message Receive End---------------")


                            #fragment_position = 0
                            #expected_seq_num = 0
                            received_fragments = []
                            size_of_message = 0
                    else:
                        print("Fragment with sequence number", rec_seq_n,
                              "was received with an error during transmission \n Sending NACK to request the fragment again")

                        ack = rec_seq_n
                        negative_ack_header = create_my_header(0, ack, 0b00010100, 0, 0)
                        sock_send.sendto(negative_ack_header, (Client2_IP, Client2_receive_PORT))




                elif rec_flags == 0b10010000:  #informacna sprava pre fragmentovanu message
                    start_time = time.time()
                    n_of_f = rec_checksum
                    received_fragments = [None] * n_of_f
                    print("\n---------------Message Receive---------------")

                    if rec_ack_n == rec_seq_n:
                        print("\nA message with a size of", rec_checksum * rec_seq_n, "will be received")
                        size_of_message = rec_checksum * rec_seq_n
                    else:
                        print("\nA message with a size of", (rec_checksum - 1) * rec_seq_n + rec_ack_n, "will be received")
                        size_of_message = (rec_checksum - 1) * rec_seq_n + rec_ack_n

                    print("The message is fragmented,\nNumber of fragments =", rec_checksum,
                          "\nSize of fragments =", rec_seq_n, "\nSize of the last fragment =", rec_ack_n,"\n")

                    expected_seq_num = rec_length_of_data
                    #fragment_position = 0

                elif rec_flags == 0b10100000:  #informacna sprava pre nefragmentovany subor
                    print("\n---------------File Receive---------------")

                    print("\nA file with the name", message.decode('utf-8'), "and size", rec_length_of_data, "will be received")
                    print("The file is not fragmented.\n")

                    filename = message.decode('utf-8')
                    size_of_file = rec_length_of_data

                elif rec_flags == 0b10110000:  #informacna sprava pre fragmentovany subor
                    start_time = time.time()
                    n_of_f = rec_checksum
                    received_fragments = [None] * n_of_f
                    filename = message.decode('utf-8')
                    print("\n---------------File Receive---------------")

                    if rec_ack_n==rec_seq_n:
                        print("\nA file with the name", message.decode('utf-8'), "and size", rec_checksum * rec_seq_n, "will be received")
                        size_of_file = rec_checksum*rec_seq_n
                    else:
                        print("\nA file with the name", message.decode('utf-8'), "and size", (rec_checksum - 1) * rec_seq_n + rec_ack_n, "will be received")
                        size_of_file = (rec_checksum-1)*rec_seq_n + rec_ack_n

                    print("The file is fragmented,\nNumber of fragments =", rec_checksum,
                          "\nSize of fragments =", rec_seq_n, "\nSize of the last fragment =", rec_ack_n,"\n")
                    expected_seq_num = rec_length_of_data
                    #fragment_position = 0


                else:        #message bez fragmentacie
                    checksum = calculate_checksum(message)#.decode('utf-8'))
                    rec_seq_n, rec_ack_n, rec_flags, rec_length_of_data, rec_checksum = struct.unpack('!HHBHH', header)
                    #print(rec_checksum, checksum, rec_seq_n)
                    print("\n---------------Message Receive---------------")

                    if checksum == rec_checksum:
                        #print("Message was received successfully")
                        ack = rec_seq_n
                        positive_ack_header = create_my_header(0, ack, 0b00000010, 0, 0)
                        sock_send.sendto(positive_ack_header, (Client2_IP, Client2_receive_PORT))
                        print("\nReceived Message: ", message.decode("utf-8"))

                        print("\n---------------Message Receive End---------------")

                    else:
                        print("The message was wrong, sending a negative acknowledgment to request the message again")
                        ack = rec_seq_n
                        negative_ack_header = create_my_header(0, ack, 0b00000100, 0, 0)
                        sock_send.sendto(negative_ack_header, (Client2_IP, Client2_receive_PORT))

        except OSError:
            break


def send_message():
    global command, seq_num, message_correct,path, sended_fragments, first_seq, probably_connection_lost,connection_active
    #global hearbeat_active
    while connection_active:
        try:

            if not command:
                com = choose_command()
                simulation = 0

            if com == 'S':
                simulation = 1
                com = 'M'

            if com == 'W':
                simulation = 1
                com = 'F'

            if com == 'M':
                fragment_size = int(input("\nEnter the maximum fragment size in the range 250 - 1400: "))
                if fragment_size == 0:
                    command = False
                else:
                    while fragment_size < 250 or fragment_size > 1400:
                        print("Size is out of range, please try again")
                        fragment_size = int(input("Enter the maximum fragment size in the range 250 - 1400: "))


                message = input("\nType your message (if you do not want to send messages anymore, type - Exit): ")
                if message == "Exit":
                    command = False
                else:

                    if len(message) <= fragment_size:  #sprava sa nebude fragmentovat
                        seq_num += 1
                        checksum = calculate_checksum(message) + simulation
                        #print(checksum, seq_num)
                        header = create_my_header(seq_num, 0, 0b00000000, len(message.encode("utf-8")), checksum)
                        sock_send.sendto(header + message.encode("utf-8"), (Client2_IP, Client2_receive_PORT))


                        print("\n---------------Message---------------")
                        print("Sent Message: ", message)

                        timeout = time.time()
                        counter = 0
                        while not message_correct:

                            if time.time() - timeout > 5:
                                if counter == 3:
                                        print("\nConnection lost")
                                        probably_connection_lost = True
                                        connection_active = False
                                        close_sockets()
                                        exit(0)
                                        #break
                                checksum = calculate_checksum(message)
                                header = create_my_header(seq_num, 0, 0b00000000, len(message.encode("utf-8")), checksum)
                                sock_send.sendto(header + message.encode("utf-8"), (Client2_IP, Client2_receive_PORT))
                                print("\nThe message was wrong or lost, sending again")
                                counter+=1
                                timeout = time.time()

                        print("\n---------------Message End---------------")
                        message_correct = False
                        command = True

                    else:  #sprava sa fragmentuje
                        fragments = []
                        for i in range(0, len(message), fragment_size):
                            fragment = message[i:i + fragment_size]
                            fragments.append(fragment)

                        sended_fragments = len(fragments) * [0]

                        n_of_fragments = len(fragments)
                        last_fragment_size = fragment_size
                        if len(message) % fragment_size != 0:
                            last_fragment_size = len(fragments[-1])


                        header = create_my_header(fragment_size, last_fragment_size, 0b10010000, seq_num + 1, n_of_fragments)
                        sock_send.sendto(header + "message".encode("utf-8"), (Client2_IP, Client2_receive_PORT))
                        time.sleep(1)

                        first_seq = seq_num + 1

                        print("\n---------------Message---------------")

                        print("\nA message with a size of", len(message), "will be sent")
                        print("The message is fragmented,\nNumber of fragments =", n_of_fragments,
                              "\nSize of fragments =", fragment_size, "\nSize of the last fragment =",
                              last_fragment_size, "\n")

                        window_size = 5
                        if n_of_fragments < window_size:
                            window_size = 2
                        #print("Windowsize: ", window_size)

                        for i, fragment in enumerate(fragments):
                            if i == window_size:
                                break
                            else:
                                checksum = calculate_checksum(fragment)
                                if i == 0:
                                    checksum = checksum + simulation
                                seq_num += 1
                                header = create_my_header(seq_num, 0, 0b00010000, len(fragment), checksum)
                                sock_send.sendto(header + fragment.encode("utf-8"), (Client2_IP, Client2_receive_PORT))
                                print("Fragment with sequence number: ", seq_num, "has been sent")

                        oldest = 0
                        timeout = time.time()
                        counter = 0

                        while 0 in sended_fragments:
                            if sended_fragments[oldest] == 1:
                                timeout = time.time()
                                if window_size > len(fragments) - 1:
                                    break

                                seq_num += 1
                                checksum = calculate_checksum(fragments[window_size])
                                header = create_my_header(seq_num, 0, 0b00010000, len(fragments[window_size]), checksum)
                                sock_send.sendto(header + fragments[window_size].encode("utf-8"), (Client2_IP, Client2_receive_PORT))
                                print("Fragment with sequence number: ", seq_num, "has been sent")

                                window_size += 1
                                oldest += 1
                                counter = 0

                            if counter == 3:
                                print("\nConnection lost")
                                probably_connection_lost = True
                                probably_connection_lost = True
                                connection_active = False
                                close_sockets()
                                exit(0)

                                #break

                            if time.time() - timeout > 5:
                                print("Fragment with sequence number: ", seq_num - (window_size - oldest) + 1, "was lost or wrong, it has been resent")

                                checksum = calculate_checksum(fragments[oldest])
                                header = create_my_header(seq_num - (window_size - oldest)+1, 0, 0b00010000, len(fragments[oldest]), checksum)
                                sock_send.sendto(header + fragments[oldest].encode("utf-8"), (Client2_IP, Client2_receive_PORT))
                                counter += 1
                                timeout = time.time()
                            time.sleep(0.01)

                        print("\nThe message was sent successfully")
                        print("\n---------------Message End---------------")
                        sended_fragments = False
                        command = True

            elif com == 'Q':
                if probably_connection_lost:
                    if connection_active:
                        connection_active = False
                    close_sockets()
                    exit(0)

                header = create_my_header(0, 0, 0b01000000, 0, 0)
                terminate(header)
                break

            elif com == 'P':
                p = 0
                while p == 0:
                    path = input("\nSet the absolute path for saving received files: ")
                    if not os.path.isdir(path):
                        p = 0
                        print("Path does not exist. Please try again.")
                    else:
                        p = 1
                command = False

            elif com == 'F':
                fragment_size = int(input("\nEnter the maximum fragment size in the range 250 - 1400(type 0 if you do not want to send files anymore): "))
                if fragment_size == 0:
                    command = False
                else:
                    while fragment_size < 250 or fragment_size > 1400:
                        print("The size is out of range, please try again.")
                        fragment_size = int(input("Enter the maximum fragment size in the range 250 - 1400(type 0 if you do not want to send files anymore): "))

                    file_path = input("\nEnter the file path to send: ")

                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    file_name = file_path.split('/')[-1]



                    if len(file_data) <= fragment_size: #subor sa nefragmentuje
                        header = create_my_header(0, 0, 0b10100000, len(file_data), 0)
                        message = os.path.basename(file_name)
                        sock_send.sendto(header + message.encode("utf-8"), (Client2_IP, Client2_receive_PORT))

                        print("\n---------------File---------------")

                        print("\nA file with the name", message, "and size", len(file_data), "will be sent")

                        time.sleep(1)

                        seq_num += 1

                        checksum = calculate_checksum(file_data) + simulation#.decode("utf-8"))
                        header = create_my_header(seq_num, 0, 0b00100000, len(file_data), checksum)
                        message = header + file_data
                        sock_send.sendto(message, (Client2_IP, Client2_receive_PORT))


                        timeout = time.time()
                        counter = 0
                        while not message_correct:
                            if time.time() - timeout > 5:
                                if counter == 3:
                                    print("\nConnection lost.")
                                    probably_connection_lost = True
                                    probably_connection_lost = True
                                    connection_active = False
                                    close_sockets()
                                    exit(0)
                                    #break
                                checksum = calculate_checksum(file_data)#.decode("utf-8"))
                                header = create_my_header(seq_num, 0, 0b00100000, len(file_data), checksum)
                                message = header + file_data
                                sock_send.sendto(message, (Client2_IP, Client2_receive_PORT))
                                print("\nThe file was lost or wrong, sending again")
                                counter += 1
                                timeout = time.time()

                        print("\nThe file was sent successfully.")
                        print("\n---------------File End---------------")
                        message_correct = False
                        command = True

                    else: #subor sa fragmentuje

                        fragments = []
                        for i in range(0, len(file_data), fragment_size):
                            fragment = file_data[i:i + fragment_size]
                            fragments.append(fragment)

                        sended_fragments = len(fragments)*[0]

                        n_of_fragments = len(fragments)
                        last_fragment_size = fragment_size
                        if len(file_data) % fragment_size != 0:
                            last_fragment_size = len(fragments[-1])

                        header = create_my_header(fragment_size, last_fragment_size, 0b10110000, seq_num+1,n_of_fragments)
                        message = os.path.basename(file_name)
                        sock_send.sendto(header + message.encode("utf-8"), (Client2_IP, Client2_receive_PORT))

                        first_seq = seq_num+1

                        print("\n---------------File---------------")

                        print("\nA file with the name", message, "and size", len(file_data), "will be sent")
                        print("The file is fragmented,\nNumber of fragments =", n_of_fragments,
                              "\nSize of fragments =", fragment_size, "\nSize of the last fragment =", last_fragment_size, "\n")

                        time.sleep(1)


                        window_size = 5 #math.ceil(len(fragments) / 10)
                        if window_size < n_of_fragments:
                            window_size = 2

                        #print("Windowsize: ", window_size)

                        for i, fragment in enumerate(fragments):
                            if i == window_size:
                                break
                            else:
                                checksum = calculate_checksum(fragment)
                                if i == 0:
                                    checksum = checksum +simulation
                                seq_num += 1
                                header = create_my_header(seq_num, 0, 0b00110000, len(fragment), checksum)
                                sock_send.sendto(header + fragment, (Client2_IP, Client2_receive_PORT))
                                print("Fragment with sequence number: ", seq_num, "has been sent")

                        oldest = 0
                        timeout = time.time()

                        counter = 0

                        while 0 in sended_fragments:
                            if sended_fragments[oldest] == 1:
                                timeout = time.time()
                                if window_size > len(fragments)-1:
                                    break

                                seq_num += 1
                                checksum = calculate_checksum(fragments[window_size])
                                header = create_my_header(seq_num, 0, 0b00110000, len(fragments[window_size]), checksum)
                                sock_send.sendto(header + fragments[window_size], (Client2_IP, Client2_receive_PORT))
                                print("Fragment with sequence number: ", seq_num, "has been sent")

                                window_size+=1
                                oldest +=1
                                counter = 0


                            if counter == 3:
                                print("\nConnection lost.")
                                probably_connection_lost = True
                                connection_active = False
                                close_sockets()
                                exit(0)
                                #break

                            if time.time() - timeout > 5:
                                print("Packet with sequence number: ", seq_num - (window_size - oldest) + 1, "was lost, it has been resent")

                                checksum = calculate_checksum(fragments[oldest])
                                header = create_my_header(seq_num-(window_size-oldest)+1, 0, 0b00110000, len(fragments[oldest]),checksum)
                                sock_send.sendto(header + fragments[oldest], (Client2_IP, Client2_receive_PORT))
                                counter +=1
                                timeout = time.time()
                            time.sleep(0.01)


                        print("\nThe file was sent successfully.")
                        print("\n---------------File End---------------")
                        sended_fragments = False
                        command = True


        except OSError:
            break

#hotovo
def handle_heartbeat():
    global heartbeat_count, connection_active

    while connection_active:
        if heartbeat_active:

            header = create_my_header(0, 0, 0b00001000, 0, 0)
            if connection:
                sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))
                #print("Sent Heartbeat")
            time.sleep(5)

            heartbeat_count += 1
            if heartbeat_count > 3:
                print("\nConnection lost. No response to Heartbeat messages.")
                connection_active = False
                close_sockets()
                break
        else:
            time.sleep(1)


def close_sockets():
    sock_send.close()
    sock_receive.close()


def handshake(header):
    global connection
    rec_seq_n, rec_ack_n, rec_flags, rec_length_of_data, rec_checksum = struct.unpack('!HHBHH', header)

    if rec_flags == 0b00000001:  #poslanie syn
        #print("Syn sa poslal")
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))

    elif rec_flags == 0b00000011: #prijatie syn, poslanie syn-ack
        #print("syn ack sa poslal")
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))

    elif rec_flags == 0b00000010: #prijatie syn-ack, poslanie ack + dokoncenie handshaku
        #print("ack sa poslal")
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))
        print("\nHandshake was successfull\n")
        connection = True
        receive_thread = threading.Thread(target=receive_message)
        receive_thread.start()

        heartbeat_thread = threading.Thread(target=handle_heartbeat())
        heartbeat_thread.start()

def terminate(header):
    global init_T, accept_T, connection_active
    rec_seq_n, rec_ack_n, rec_flags, rec_length_of_data, rec_checksum = struct.unpack('!HHBHH', header)

    if rec_flags == 0b01000000:  #poslanie fin
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))
        #print("fin send")
    elif rec_flags == 0b01000010: #prijatie fin, poslanie ack-fin
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))
        accept_T = True
        #print("ackfin send")
        if init_T and accept_T:
            print("\nTermination handshake completed. Closing connection.")
            connection_active = False
            close_sockets()
            exit(0)
        T_header = create_my_header(0, 0, 0b01000000, 0, 0) #poslanie fin
        terminate(T_header)


def connect():
    global connection_active
    print("\nType H if you want to connect by performing Handshake ")
    print("Type Q if you want to terminate program ")

    command = input()
    if command == 'H':
        first_header = create_my_header(0, 0, 0b00000001, 0, 0)
        handshake(first_header)
        start_time = time.time()

        while not connection:
            if time.time() - start_time > 5:
                print("\nNo response received during handshake. Retry to connect...")
                connect()
                start_time = time.time()

    elif command == "Q":
        connection_active = False
        close_sockets()
        receive_thread.join()
        exit(0)


def choose_command():
    global heartbeat_active

    if not connection_active:
        return None

    heartbeat_active = True

    print("\nChoose what do you want to perform")
    print ("M - Send MESSAGE")
    print("F - Send FILE")
    print("S - Simulate transmission ERROR for a MESSAGE")
    print("W - Simulate transmission ERROR for a FILE")
    print("P - Change the save path")
    print("Q - Terminate program")




    com = input()

    if com != 'P':  #pozastavenie heartbeatu
        header = create_my_header(0, 0, 0b00001100, 0, 0)
        sock_send.sendto(header, (Client2_IP, Client2_receive_PORT))
        heartbeat_active = False

    return com


if __name__ == "__main__":

    global Client1_IP, Client1_receive_PORT, Client1_send_PORT, Client2_IP, Client2_receive_PORT, Client2_send_PORT, path


    Client1_IP = input("IP of client 1 (you): ")
    Client1_receive_PORT = int(input("Recieve port of client 1 (you): "))
    Client1_send_PORT = int(input("Send port of client 1 (you): "))
    Client2_IP = input("IP of client 2: ")
    Client2_receive_PORT = int(input("Recieve port of client 2: "))
    Client2_send_PORT = int(input("Send port of client 2: "))



    p = 0
    while p==0:
        path = input("Set the absolute path for saving received files: ")
        if not os.path.isdir(path):
            p=0
            print("Path does not exist. Please try again.")
        else:
            p=1



    sock_receive, sock_send = initialize_sockets()

    receive_thread = threading.Thread(target = receive_message)
    receive_thread.start()

    connect()

    send_thread = threading.Thread(target=send_message)
    send_thread.start()

    #heartbeat_thread.join()
    #send_thread.join()
    #receive_thread.join()
    #close_sockets()
