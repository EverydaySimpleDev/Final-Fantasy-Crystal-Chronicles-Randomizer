"""
othergender.py - an "Other" choice on the character-creation gender screen,
with neutral wording ("they") in the game's gendered text. Every ISO the
patcher builds gets it.

How the game handles gender
---------------------------
A character's gender is m_genderFlag (+0x3E2 in its caravan record), 0 male
or 1 female. The game uses it as an index for the model, the animations and
the letters it sends, so a third value would break those. An Other character
is therefore saved as male, and byte 15 of its 16-byte name (+0x3D9, always
0 since names stop at 8 characters, and kept by the save) marks it as Other.
It plays and looks like a male character.

The menu (Start.dol, NTSC-US)
-----------------------------
The gender screen's up/down toggle (m_select ^= 1, 0x80172E54) cycles through
three choices, CmakeSexDraw draws three lines (the third is "Other") on a
taller parchment, and
confirming an Other choice stores gender 0 plus a marker in
s_CmakeInfo.m_name[0x11]. The confirm screens print "Other", and creating
the character copies the marker into name byte 15.

The text
--------
Gendered text is written `FF E4 male FF E6 female FF E7` (the gender of the
character the message is about) or `FF E5 <who> ...` (a caravan member). The
patch teaches both text engines (CMes::addString for dialogue,
CMes::MakeAgbString for letters) a third part, `... FF E6 female FF F1
neutral FF E7`: an Other character sees only the neutral part, everyone else
sees what they always did. Op 0x51 (FF F1) is unused by the game. The
gendered lines get their neutral part in TEXT_EDITS, including the farewell
scene's "son" messages (FAREWELL_EDITS). The .cfd files grow by
a few bytes, so they are written back with gciso.put_file.

The new code lives in MetroTRK debugger functions the game never calls:
TRKDispatchMessage (0x801A8F64) and TRKDoSetOption/TRKDoStop (0x801A90DC).

    py othergender.py apply <iso>
"""

import os
import sys
import tempfile

# Start.dol: (offset, original bytes, new bytes)
_REGION_1 = bytes.fromhex(
    "4f746865" "72000000"   # "Other", then the dialogue flag and the letter flag
    # mes_gender (addString ops 0x44/0x45 jump here with r3 = the caravan records + member * 0xC30)
    "880317c9"   # lbz   r0, 0x17C9(r3)     the member's Other marker (name byte 15)
    "3d80801b"   # lis   r12, flag@ha
    "980c8f6a"   # stb   r0, flag@l(r12)    kept until the branch ends
    "2c000000"   # cmpwi r0, 0
    "3b200002"   # li    r25, 2             hide the male part
    "40820014"   # bne   out                Other: hide the male and the female parts
    "a00317d2"   # lhz   r0, 0x17D2(r3)     the gender (the instruction this replaced)
    "28000000"   # cmplwi r0, 0
    "40820008"   # bne   out                female: hide the male part
    "3b200001"   # li    r25, 1             male: show it
    "4bef1844"   # out: b 0x8009A7D8        the end of the tag
    # mes_else (op 0x46)
    "3d80801b"   # lis   r12, flag@ha
    "898c8f6a"   # lbz   r12, flag@l(r12)
    "2c0c0000"   # cmpwi r12, 0
    "4082fff0"   # bne   out                Other: the female part stays hidden
    "5720063e"   # clrlwi r0, r25, 24       (the instruction this replaced)
    "4bef153c"   # b     0x8009A4E8
    # mes_end (op 0x47)
    "3b200000"   # li    r25, 0             (the instruction this replaced)
    "38000000"   # li    r0, 0
    "3d80801b"   # lis   r12, flag@ha
    "980c8f6a"   # stb   r0, flag@l(r12)    the branch is over
    "4bef1818"   # b     0x8009A7D8
    # mes_neutral (op 0x51, from the jump table)
    "3d80801b"   # lis   r12, flag@ha
    "898c8f6a"   # lbz   r12, flag@l(r12)
    "3b200002"   # li    r25, 2             hide the neutral part
    "2c0c0000"   # cmpwi r12, 0
    "4182ffc0"   # beq   out
    "3b200001"   # li    r25, 1             unless the member is Other
    "4bef17fc"   # b     0x8009A7D8
    # agb_gender, agb_else, agb_end, agb_neutral: the same for MakeAgbString (state in r28)
    "880317c9"   # lbz   r0, 0x17C9(r3)
    "3d80801b"   # lis   r12, flag@ha
    "980c8f6b"   # stb   r0, flag@l(r12)
    "2c000000"   # cmpwi r0, 0
    "3b800002"   # li    r28, 2
    "40820014"   # bne   out
    "a00317d2"   # lhz   r0, 0x17D2(r3)
    "28000000"   # cmplwi r0, 0
    "40820008"   # bne   out
    "3b800001"   # li    r28, 1
    "4beef53c"   # out: b 0x80098544
    "3d80801b"   # lis   r12, flag@ha
    "898c8f6b"   # lbz   r12, flag@l(r12)
    "2c0c0000"   # cmpwi r12, 0
    "4082fff0"   # bne   out
    "5780063e"   # clrlwi r0, r28, 24
    "4beef474"   # b     0x80098494
    "3b800000"   # li    r28, 0
    "38000000"   # li    r0, 0
    "3d80801b"   # lis   r12, flag@ha
    "980c8f6b"   # stb   r0, flag@l(r12)
    "4beef510"   # b     0x80098544
    "3d80801b"   # lis   r12, flag@ha
    "898c8f6b"   # lbz   r12, flag@l(r12)
    "3b800002"   # li    r28, 2
    "2c0c0000"   # cmpwi r12, 0
    "4182ffc0"   # beq   out
    "3b800001"   # li    r28, 1
    "4beef4f4"   # b     0x80098544
    # sexstr: CmakeSexDraw's GetMenuStr(0x11 + line)
    "2c040013"   # cmpwi r4, 0x13           the third line
    "4082002c"   # bne   GetMenuStr
    "3c60801b"   # lis   r3, "Other"@ha
    "38638f64"   # addi  r3, r3, "Other"@l
    "4e800020"   # blr
    # resultstr: the confirm screens' GetMenuStr(gender + 0x11)
    "3d808031"   # lis   r12, 0x8031
    "898cab49"   # lbz   r12, -0x54B7(r12)  s_CmakeInfo.m_name[0x11], the Other marker
    "2c0c0000"   # cmpwi r12, 0
    "41820010"   # beq   GetMenuStr         Male or Female
    "3c60801b"   # lis   r3, "Other"@ha
    "38638f64"   # addi  r3, r3, "Other"@l
    "4e800020"   # blr
    "4bf9b58c"   # GetMenuStr: b 0x80144610
)
_REGION_1_ORIG = bytes.fromhex(
    "9421fff07c0802a6388000009001001493e1000c3be0050093c100087c7e1b784bfffa613c60801e88be0014"
    "388356d8386000014cc6318248005541881e00142800001a418100f83c6080225400103a3863bde07c03002e"
    "7c0903a64e8004207fc3f3784800105d7c7f1b78480000d07fc3f37848000fd57c7f1b78480000c07fc3f378"
    "48000f6d7c7f1b78480000b07fc3f37848000f057c7f1b78480000a07fc3f37848000eed7c7f1b7848000090"
    "7fc3f37848000ed57c7f1b78480000807fc3f37848000c817c7f1b78480000707fc3f37848000a357c7f1b78"
    "480000607fc3f378480007457c7f1b78480000507fc3f378480004a57c7f1b78480000407fc3f378480003e5"
    "7c7f1b78480000307fc3f378480001b57c7f1b78480000207fc3f378"
)
_REGION_2 = bytes.fromhex(
    # cycle: the gender screen's up/down (r0 = the cursor, r27 = the D-pad bits)
    "7c0c0378"   # mr    r12, r0            0 Male, 1 Female, 2 Other
    "73600004"   # andi. r0, r27, 4         down?
    "41820018"   # beq   up
    "398c0001"   # addi  r12, r12, 1
    "2c0c0003"   # cmpwi r12, 3
    "4180001c"   # blt   out
    "39800000"   # li    r12, 0             wrap to Male
    "48000014"   # b     out
    "398cffff"   # up: addi r12, r12, -1
    "2c0c0000"   # cmpwi r12, 0
    "40800008"   # bge   out
    "39800002"   # li    r12, 2             wrap to Other
    "7d806378"   # out: mr r0, r12
    "4e800020"   # blr
    # confirm: s_CmakeInfo.m_gender = the cursor (r6), r5 = s_CmakeInfo
    "39800000"   # li    r12, 0
    "2c060002"   # cmpwi r6, 2              Other?
    "4082000c"   # bne   store
    "38c00000"   # li    r6, 0              Other plays as male
    "39800001"   # li    r12, 1
    "98c50012"   # store: stb r6, 0x12(r5)  s_CmakeInfo.m_gender
    "99850011"   # stb   r12, 0x11(r5)      s_CmakeInfo.m_name[0x11], the Other marker
    "4e800020"   # blr
    # create: the new character (r28) gets its gender, r29 = s_CmakeInfo
    "b01c03e2"   # sth   r0, 0x3E2(r28)     m_genderFlag (the instruction this replaced)
    "899d0011"   # lbz   r12, 0x11(r29)     the Other marker
    "999c03d9"   # stb   r12, 0x3D9(r28)    into name byte 15, which the save keeps
    "4e800020"   # blr
)
_REGION_2_ORIG = bytes.fromhex(
    "9421ffb07c0802a63c80801e9001005493e1004c3be4571893c10048880300188bc3001c2800000140820030"
    "387f00004bfffdd1281e000041820010387f00204bfffdc14800000c387f00284bfffdb57fc3f37848004421"
    "386100083880000038a000404be5c2cd"
)

OTHER_GENDER_PATCHES = [
    (0x198d04, _REGION_1_ORIG, _REGION_1),
    (0x198e7c, _REGION_2_ORIG, _REGION_2),
    (0x8a07c, bytes.fromhex("a00317d2"), bytes.fromhex("4810ec90")),    # addString op 0x44: b mes_gender
    (0x8a140, bytes.fromhex("a00317d2"), bytes.fromhex("4810ebcc")),    # addString op 0x45: b mes_gender
    (0x8a284, bytes.fromhex("5720063e"), bytes.fromhex("4810eab4")),    # addString op 0x46: b mes_else
    (0x8a35c, bytes.fromhex("3b200000"), bytes.fromhex("4810e9f4")),    # addString op 0x47: b mes_end
    (0x20b7d8, bytes.fromhex("8009a7d8"), bytes.fromhex("801a8fc4")),   # addString jump table, op 0x51: mes_neutral
    (0x881bc, bytes.fromhex("a00317d2"), bytes.fromhex("48110bc4")),    # MakeAgbString op 0x44: b agb_gender
    (0x88230, bytes.fromhex("5780063e"), bytes.fromhex("48110b7c")),    # MakeAgbString op 0x46: b agb_else
    (0x88254, bytes.fromhex("3b800000"), bytes.fromhex("48110b70")),    # MakeAgbString op 0x47: b agb_end
    (0x20b518, bytes.fromhex("80098544"), bytes.fromhex("801a9038")),   # MakeAgbString jump table, op 0x51: agb_neutral
    (0x15ff00, bytes.fromhex("4bfd44b1"), bytes.fromhex("48038ef5")),   # CmakeSexDraw: bl sexstr
    (0x15ff60, bytes.fromhex("2c1d0002"), bytes.fromhex("2c1d0003")),   # CmakeSexDraw: three lines
    # CmakeSexDraw: the parchment's height scale was the width's (fmr f8, f7, 0.615).
    # It becomes the game's 0.8 constant, so the parchment is tall enough for three lines.
    (0x15fe24, bytes.fromhex("fd003890"), bytes.fromhex("c102b6ec")),   # lfs f8, -0x4914(r2)
    (0x162bf4, bytes.fromhex("68000001"), bytes.fromhex("48036289")),   # gender screen: bl cycle (was xori r0, r0, 1)
    (0x162c3c, bytes.fromhex("98c50012"), bytes.fromhex("48036279")),   # gender screen: bl confirm
    (0x163094, bytes.fromhex("b01c03e2"), bytes.fromhex("48035e41")),   # new character: bl create
    (0x15d58c, bytes.fromhex("4bfd6e25"), bytes.fromhex("4803b87d")),   # CmakeResultDraw1: bl resultstr
    (0x15e0ac, bytes.fromhex("4bfd6305"), bytes.fromhex("4803ad5d")),   # CmakeResultDraw: bl resultstr
]

# The game's text
E4 = b"\xff\xe4"           # the character the message is about
E5 = b'\xff\xe5 "'         # the caravan member in variable 2 (the one the family talks about)
E5_LEAVING = b"\xff\xe5 !"  # the caravan member in variable 1 (the one setting out, in farewell.cfd)


def branch(op, male, female, neutral=None):
    """A gendered part of a message, with the neutral part when given."""
    out = op + male + b"\xff\xe6" + female
    if neutral is not None:
        out += b"\xff\xf1" + neutral
    return out + b"\xff\xe7"


# The farewell scene picks a "son" or a "daughter" message by gender, so an
# Other character gets the "son" one. Those get branches of their own.
FAREWELL_EDITS = [
    edit
    for message in (7, 9, 11)       # with no, one or two siblings
    for edit in (
        (message, b"'s son,", b"'s " + branch(E5_LEAVING, b"son", b"daughter", b"child") + b","),
        (message, b"his ", branch(E5_LEAVING, b"his", b"her", b"their") + b" "),
    )
]

# {file: [(message, original, with the neutral part)]}. Every copy of the
# original in the message changes. A verb that changes with "they" moves
# inside the branch.
TEXT_EDITS = {
    "dvd/cft/village.cfd": [
        (106, branch(E5, b"his", b"her"), branch(E5, b"his", b"her", b"their")),
        (108, branch(E5, b"himself", b"herself"), branch(E5, b"himself", b"herself", b"themself")),
        (108, branch(E5, b"He's a good boy", b"She's a good girl"),
         branch(E5, b"He's a good boy", b"She's a good girl", b"They're a good kid")),
        (109, branch(E5, b"he", b"she") + b" misses",
         branch(E5, b"he misses", b"she misses", b"they miss")),
        (110, branch(E5, b"him", b"her"), branch(E5, b"him", b"her", b"them")),
        (111, branch(E5, b"his", b"her"), branch(E5, b"his", b"her", b"their")),
        (112, branch(E5, b"he", b"she") + b" is well",
         branch(E5, b"he is", b"she is", b"they are") + b" well"),
        (118, branch(E5, b"he", b"she"), branch(E5, b"he", b"she", b"they")),
        (136, branch(E5, b"him", b"her") + b"self", branch(E5, b"him", b"her", b"them") + b"self"),
        (136, branch(E5, b"him that his", b"her that her"),
         branch(E5, b"him that his", b"her that her", b"them that their")),
        (136, branch(E5, b"him", b"her") + b"!", branch(E5, b"him", b"her", b"them") + b"!"),
        (137, branch(E5, b"He's", b"She's"), branch(E5, b"He's", b"She's", b"They're")),
        (137, b"is " + branch(E5, b"he", b"she") + b"?",
         branch(E5, b"is he", b"is she", b"are they") + b"?"),
    ],
    "dvd/cft/kai_xxx.cfd": [
        (159, branch(E4, b"He's", b"She's"), branch(E4, b"He's", b"She's", b"They're")),
        (159, branch(E4, b"his", b"her"), branch(E4, b"his", b"her", b"their")),
    ],
    "dvd/cft/kai_cas.cfd": [
        (74, branch(E4, b"he", b"she"), branch(E4, b"he", b"she", b"they")),
    ],
    "dvd/cft/farewell.cfd": FAREWELL_EDITS,
    "dvd/cft/c_system.cfd": [
        (604, branch(E4, b"man", b"woman"), branch(E4, b"man", b"woman", b"person")),
        (662, branch(E4, b"man", b"lady"), branch(E4, b"man", b"lady", b"one")),
        (854, branch(E4, b"man", b"woman"), branch(E4, b"man", b"woman", b"person")),
    ],
}


def _edit_text(iso):
    """Add the neutral parts. Returns how many were added (0 if already there)."""
    import gciso
    import randomizer
    added = 0
    for disc, edits in TEXT_EDITS.items():
        tmp = os.path.join(tempfile.gettempdir(), "othergender_" + os.path.basename(disc))
        randomizer._extract(iso, disc, tmp)
        chunks, messages = randomizer._cfd_messages(open(tmp, "rb").read())
        changed = False
        for index, old, new in edits:
            message = messages[index]
            if new in message:
                continue
            if old not in message:
                raise ValueError(f"{disc} message {index}: unexpected text, can't add the neutral wording")
            messages[index] = message.replace(old, new)
            changed = True
            added += 1
        if changed:
            gciso.put_file(iso, disc, randomizer._cfd_build(chunks, messages))
    return added


def apply(iso):
    """The Other gender choice and its neutral wording. Safe to run again."""
    import randomizer
    randomizer._dol_patch(iso, OTHER_GENDER_PATCHES, "other-gender")
    return _edit_text(iso)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "apply":
        sys.exit(__doc__)
    n = apply(sys.argv[2])
    print(f"Other gender: in place ({n} neutral wording(s) added)")
