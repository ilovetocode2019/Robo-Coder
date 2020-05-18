bad_fellings = ["bad", "sad", "horrible", "upset", "down", "sick", "unhappy", "😦", "☹️", "🙁"]
okay_fellings = ["so-so", "okay", "ok", "fine", "👌", "😐", "😶"]
good_fellings = ["good", "happy", "amazing", "well", "exited", "glad", "great", "😄", "😃", "🙂"]
relaxed_fellings = ["relaxed","chill", "cool", "rested", "restfull", "tired"]
mad_fellings = ["mad", "angry", "raged", "disgusted", "annoyed", "frustrated", "😠", "😡", "😈"]
mode = [2, "normal"]
fellings = bad_fellings + okay_fellings + good_fellings + relaxed_fellings  + mad_fellings
def modeDetector(message, pos):
    global mode
    print(mode)
    print("emotion detecting")
    if pos == 0:
        if message[pos] in good_fellings:
            return "good", 2
        elif message[pos] in bad_fellings:
            return "bad", 2
        elif message[pos] in okay_fellings:
            return "okay", 2
        elif message[pos] in relaxed_fellings:
            return "relaxed", 2
        elif message[pos] in mad_fellings:
            return "mad", 2
    #letters_before = message[pos-2]+" "+message[pos-1]
    letter_before = message[pos-1]
    if letter_before in ["mostly", "alot"]:
        mode = [2, "normal"]
    if letter_before in ["little"] or mode == [1, "normal"]:
        mode = [1, "normal"]
        if message[pos] in good_fellings:
            return "good", 1
        if message[pos] in bad_fellings:
            return "bad", 1
        elif message[pos] in okay_fellings:
            return okay, 1
        elif message[pos] in relaxed_fellings:
            return "relaxed", 1
        elif message[pos] in mad_fellings:
            return "mad", 1
    opposite = False
    if  pos-3 >= 0:
        backPos = pos-3
    else:
        backPos = 0
    flippedMessage = message[backPos:pos]
    flippedMessage.reverse()
    for x in flippedMessage:
        if x in ["not", "no"]:
            opposite = True
            break
        elif x in fellings:
            break
    if opposite or mode == [2, "not"]:
        mode = [2, "not"]
        print("IS oppossite")
        if message[pos] in bad_fellings:
            return "okay", 2
        if message[pos] in good_fellings:
            return "bad", 2
        if message[pos] in okay_fellings:
            return "bad", 2
        elif message[pos] in relaxed_fellings:
            return "happy", 2
        elif message[pos] in mad_fellings:
            return "relaxed", 2
    if message[pos] in good_fellings:
        return "good", mode[0]
    elif message[pos] in bad_fellings:
        return "bad", mode[0]
    elif message[pos] in okay_fellings:
        return "okay", mode[0]
    elif message[pos] in relaxed_fellings:
        return "relaxed", mode[0]
    elif message[pos] in mad_fellings:
        return "mad", mode[0]
def detectFelling(message):
    #mode = [2, "normal"]
    message = message.split()
    #print(message)
    pos = 0
    fellingFromMessage = []
    for word in message:
        add = False
        for x in fellings:
            if word == x or word == x+"." or word == x+"," or word == x+"!":
                add  = True
                message[pos] = x
                break
        if add == True:
            #print(modeDetector(message, pos))
            fellingFromMessage.append(modeDetector(message, pos))
            #print(pos)
        pos += 1
    #print(fellingFromMessage)
    return fellingFromMessage
def format(data, message):
    OneFellings = []
    TwoFellings = []
    okayFellings = []
    for item in data:
        #print(item)
        if item[0] == "okay":
            okayFellings.append("okay")
        elif item[1] == 2:
            TwoFellings.append(item[0])
        elif item[1] == 1:
            OneFellings.append(item[0])
    if len(TwoFellings)>0:
        if all(x == TwoFellings[0] for x in TwoFellings) == False:
            return "okay"
        return TwoFellings[0]
    elif len(OneFellings)>0:
        if all(x == OneFellings[0] for x in OneFellings) == False:
            return "okay"
        return OneFellings[0]
    elif len(okayFellings)>0:
        return "okay"
    else:
        return "Bleep Bloop: I have no idea what \"" + message + "\" means"
        
def emotion_finder(text):
    data = detectFelling(text)
    return format(data, text)
#print(emotion(input("How are you?")))
def howAreYou_detecting(msg):
    if "you?" in msg:
        return True
