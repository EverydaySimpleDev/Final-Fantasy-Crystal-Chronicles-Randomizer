@ The GBA program's own functions and variables that gba_loot.c uses (US
@ ffcc_cli.bin, names from the decomp's gba/config/GCCE01/cli/symbols.txt).
@ Functions are marked as Thumb so the linker calls them with a plain bl.
    .syntax unified
    .thumb
    .macro fn name, addr
    .global \name
    .thumb_set \name, \addr
    .endm
    .macro var name, addr
    .global \name
    .set \name, \addr
    .endm
    fn m4aSongNumStart,    0x0201B084
    fn Screen_Reset,       0x02005844
    fn Bg_ClearMaps,       0x02000990
    fn ScouterScreen_Main, 0x02015828
    fn Scouter_SetDirty,   0x02015C88
    fn StatusWin_DrawIcon, 0x020094DC
    fn Text_SetFill,       0x02003394
    fn Text_Clear,         0x020033F4
    fn Text_Print,         0x02003464
    fn Text_SetX,          0x020038F4
    fn Window_PutText,     0x020059A4
    fn Msg_GetItemName,    0x0201A8D0
    fn Msg_GetMonsterName, 0x0201A8EC
    var gWindows,          0x030030B0
    var gRadarType,        0x03002ED0
