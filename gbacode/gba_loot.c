/* GBA side of the loot pages (see gbaloot.py). Press A on the radar to open
   them: the dungeon's end-of-stage bonus pool, one tier per page, and the
   artifacts this area's enemies carry, with the enemy that carries each.
   A turns the page, B goes back to the radar.

   The pages are drawn in the scouter's window: while they are open the radar
   kind is set to Scouter, so the game sets up and tears down that window,
   and the scouter's main function is replaced by Loot_Main. The data comes
   after the scouter records in LIST_BUF (see gc_loot.c). */

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef short s16;
typedef int s32;
typedef unsigned int u32;

struct WinItem { s16 enabled; s16 drawn; char *text; };
struct Window {
    u8 active, anim;
    s8 cursor, style, variant, bg, slot, textX, skipRows, tallRows, keepFrame;
    u8 pad[3];
    s16 rows, x, y, width, height;
    struct WinItem items[11];
};

extern struct Window gWindows[5];
extern u8 gRadarType;

void m4aSongNumStart(u16 n);
void Screen_Reset(void);
void Bg_ClearMaps(void);
s32 ScouterScreen_Main(void);
void Scouter_SetDirty(s32 active);
void StatusWin_DrawIcon(s32 idx);
void Text_SetFill(s32 on, s32 no);
void Text_Clear(void);
s32 Text_Print(const char *str, s32 mode);
void Text_SetX(s32 x);
void Window_PutText(struct Window *win, s32 row, s32 unused);
char *Msg_GetItemName(s32 idx);
char *Msg_GetMonsterName(s32 idx);

/* Which pages to show, set by the patcher: bit 0 the bonus pool, bit 1 the
   enemy drops. It is the first byte of the code (gba.ld). */
#define SHOW_BONUS_POOL  1
#define SHOW_ENEMY_DROPS 2
__attribute__((section(".loot_config"))) volatile const u8 gLootPages[4] = {
    SHOW_BONUS_POOL | SHOW_ENEMY_DROPS, 0, 0, 0
};

#define LOOT           ((const u8 *)0x02038A00)
#define RADAR_SCOUTER  2
#define A_BUTTON       1
#define B_BUTTON       2
/* In single player the game ignores the GBA's buttons (gMenuHasInput is 0 and
   the key variables are cleared), so the pages read the buttons themselves. */
#define REG_KEYINPUT   (*(volatile u16 *)0x04000130)
#define ROWS           7
#define DROPS_PER_PAGE 2
#define MAX_DROPS      20
#define ITEM_NAMES     501

static u8 sOpen;
static u8 sSavedType;
static u8 sPage;
static u8 sDirty;
static u16 sKeysHeld;

/* buttons pressed since the last call */
static u32 new_keys(void)
{
    u16 keys = ~REG_KEYINPUT & 0x3FF;
    u32 pressed = keys & ~sKeysHeld;
    sKeysHeld = keys;
    return pressed;
}

static u32 get16(const u8 *p)
{
    return p[0] | (p[1] << 8);
}

static char *put_str(char *d, const char *s)
{
    while (*s)
        *d++ = *s++;
    *d = 0;
    return d;
}

static char *put_num(char *d, u32 n)
{
    /* no division: the game's divide routines use an older calling convention */
    static const u32 tens[] = {10000, 1000, 100, 10, 1};
    s32 i, started = 0;
    for (i = 0; i < 5; i++) {
        char c = '0';
        while (n >= tens[i]) {
            n -= tens[i];
            c++;
        }
        if (c != '0' || started || i == 4) {
            *d++ = c;
            started = 1;
        }
    }
    *d = 0;
    return d;
}

static const char *item_name(u32 id)
{
    if (id == 0 || id >= ITEM_NAMES)
        return "-";
    return Msg_GetItemName(id);
}

static void put_row(s32 row, const char *text, s32 x)
{
    struct Window *win = &gWindows[1];
    Text_SetFill(0, 0);
    Text_Clear();
    if (text) {
        Text_SetX(x);
        Text_Print(text, 0);
    }
    win->bg--;
    Window_PutText(win, row, 0);
    win->bg++;
}

static s32 pool_pages(void)
{
    return (gLootPages[0] & SHOW_BONUS_POOL) && LOOT[2] != 0xFF ? 4 : 0;
}

/* the distinct (artifact, enemy kind) pairs carried, with how many enemies
   of that kind carry it */
static s32 drop_list(u16 *ids, u8 *monsters, u8 *counts)
{
    s32 n = 0, i, k;
    s32 total = LOOT[44];
    for (i = 0; i < total && i < MAX_DROPS; i++) {
        const u8 *e = LOOT + 46 + 4 * i;
        u16 id = get16(e);
        u8 monster = e[2];
        for (k = 0; k < n && (ids[k] != id || monsters[k] != monster); k++)
            ;
        if (k == n) {
            ids[n] = id;
            monsters[n] = monster;
            counts[n] = 0;
            n++;
        }
        counts[k]++;
    }
    return n;
}

static s32 drop_pages(void)
{
    u16 ids[MAX_DROPS];
    u8 monsters[MAX_DROPS], counts[MAX_DROPS];
    s32 drops, pages = 1;
    if (!(gLootPages[0] & SHOW_ENEMY_DROPS))
        return 0;
    drops = drop_list(ids, monsters, counts);
    while (drops > pages * DROPS_PER_PAGE)
        pages++;
    return pages;
}

static void draw_pool_page(s32 page)
{
    char buf[48];
    char *p;
    s32 i;

    p = put_str(buf, "Bonus tier ");
    put_num(p, page + 1);
    put_row(0, buf, 0);
    for (i = 0; i < 4; i++)
        put_row(1 + i, item_name(get16(LOOT + 12 + 2 * (4 * page + i))), 8);
    p = put_str(buf, "Needs ");
    p = put_num(p, get16(LOOT + 4 + 2 * page));
    put_str(p, " points");
    put_row(5, buf, 8);
}

static void draw_drop_page(s32 page)
{
    char buf[48];
    char *p;
    u16 ids[MAX_DROPS];
    u8 monsters[MAX_DROPS], counts[MAX_DROPS];
    s32 i, n = drop_list(ids, monsters, counts);

    p = put_str(buf, "Enemy drops ");
    p = put_num(p, page + 1);
    p = put_str(p, "/");
    put_num(p, drop_pages());
    put_row(0, buf, 0);
    for (i = 0; i < DROPS_PER_PAGE; i++) {
        s32 k = page * DROPS_PER_PAGE + i;
        if (k < n) {
            put_row(1 + 2 * i, item_name(ids[k]), 8);
            p = put_str(buf, Msg_GetMonsterName(monsters[k]));
            if (counts[k] > 1) {
                p = put_str(p, " x");
                put_num(p, counts[k]);
            }
            put_row(2 + 2 * i, buf, 20);
        } else {
            put_row(1 + 2 * i, k == 0 ? "No artifacts" : 0, 8);
            put_row(2 + 2 * i, 0, 0);
        }
    }
    put_row(5, 0, 0);
}

static void draw_page(void)
{
    s32 pool = pool_pages();
    if (sPage < pool)
        draw_pool_page(sPage);
    else
        draw_drop_page(sPage - pool);
    put_row(ROWS - 1, "A: next   B: back", 0);
}

static s32 can_open(void)
{
    return LOOT[0] == 'L' && LOOT[1] == 'T' && pool_pages() + drop_pages() > 0;
}

static void open_pages(void)
{
    m4aSongNumStart(0);
    sOpen = 1;
    sSavedType = gRadarType;
    gRadarType = RADAR_SCOUTER;
    sPage = 0;
    sDirty = 1;
    Screen_Reset();
    Bg_ClearMaps();
}

static void close_pages(void)
{
    sOpen = 0;
    gRadarType = sSavedType;
    Screen_Reset();
    Bg_ClearMaps();
}

/* every frame on the radar (replaces RadarScreen_Main's StatusWin_DrawIcon(0) call) */
void Loot_RadarFrame(s32 idx)
{
    StatusWin_DrawIcon(idx);
    if ((new_keys() & A_BUTTON) && can_open())
        open_pages();
}

/* replaces the call to ScouterScreen_Main in FieldMode_Update */
s32 Loot_Main(void)
{
    u32 keys;

    if (!sOpen) {
        /* the Scouter radar opens the pages with A too */
        if ((new_keys() & A_BUTTON) && can_open()) {
            open_pages();
            return 0;
        }
        return ScouterScreen_Main();
    }
    StatusWin_DrawIcon(0);
    if (gRadarType != RADAR_SCOUTER) {
        sOpen = 0;
        return 0;
    }
    if (sDirty) {
        if (sPage >= pool_pages() + drop_pages())
            sPage = 0;
        draw_page();
        sDirty = 0;
    }
    keys = new_keys();
    if (keys & A_BUTTON) {
        m4aSongNumStart(0);
        sPage++;
        sDirty = 1;
    } else if (keys & B_BUTTON) {
        m4aSongNumStart(3);
        close_pages();
    }
    return 0;
}

/* replaces Scouter_OnInfo's Scouter_SetDirty(1): the message now also comes
   with the other radar kinds, whose screens don't have the scouter window */
void Loot_OnScouterInfo(s32 active)
{
    if (sOpen)
        sDirty = 1;
    else if (gRadarType == RADAR_SCOUTER)
        Scouter_SetDirty(active);
}
