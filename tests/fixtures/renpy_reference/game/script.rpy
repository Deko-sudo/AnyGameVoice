define e = Character("Ena")
define s = Character("Sol")
default player_name = "Robin"
default score = 7

label start:
    voice "voice/beacon.wav"
    e "Do you hear the beacon?"  # voiced: existing clip to replace and restore
    "Fog rolls across the dock."  # narration: no explicit speaker
    s "I'm listening."  # punctuation: apostrophe inside a double-quoted string
    e "Stand by."  # repeated: same text, diff speaker
    s "Stand by."  # repeated: same text, diff speaker
    e "Mark the tide."  # repeated: same speaker, diff line_no

    e "{b}важное{/b}"  # tag: bold, preserve the enclosed word
    s "{i}курсив{/i}"  # tag: italic, preserve the enclosed word
    e "{color=#f00}красное{/color}"  # tag: a hash inside the colour value
    s "[player_name]"  # substitution: a whole line containing the player name
    e "[score]"  # substitution: a whole line containing the score
    e "At the helm: {b}[player_name]{/b}."  # substitution: name inside bold
    s "Gauge reading: {i}[score]{/i}."  # substitution: score inside italic
    "Watch log: [player_name] / [score]."  # narration: both substitutions on one line
    e "He said \"hi\"."  # escaping: literal quotation marks in dialogue
    s "Берег уже близко."  # Unicode: a complete Russian sentence
    e "灯台が見えます。"  # Unicode: Japanese characters and punctuation
    "One light is still burning 🏮."  # Unicode: emoji in narration
    s ""  # filtered: empty spoken line
    e "{b}{/b}"  # filtered: only formatting remains

    menu:
        "Follow the bell":  # choice label: not spoken
            e "The bell hangs above the steps."  # branch: option A, must survive
            s "Three rings mean high water."  # branch: option A, second speaker
        "Follow the light":  # choice label: not spoken
            s "The lamp points to the breakwater."  # branch: option B, must survive
            "A green flash crosses the channel."  # branch: option B, narration

    e "Mark the tide."  # repeated: same speaker, diff line_no
    s "Write {b}one{/b} mark beside {i}two{/i}."  # tags: two separate spans
    "The chart shows a # beside the pier."  # punctuation: hash inside dialogue
    s "Ready, [player_name]?"  # substitution: name followed by punctuation
    e "Close the log."  # dialogue: final line before return
    return
