/* GameCube side of the GBA loot pages (see gbaloot.py). Called instead of
   GbaQueue::GetScouterInfo when the scouter message is built: after the 64
   scouter records (0x200 bytes) it adds a 0x80-byte block for the GBA:

     0  'L' 'T'
     2  cycle step (0-2), 0xFF outside a dungeon
     3  stage
     4  the 4 bonus tier thresholds (u16, GBA byte order)
     12 the 16 bonus pool items: 4 rows of 4 (u16)
     44 number of artifact drops
     46 the artifacts carried by this area's living enemies, up to 20 of
        (artifact u16, enemy kind u8, 0) */

typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;

int GetScouterInfo(void *que, int channel, u8 *out);

#define GAME          0x8021DE80
#define STAGE_INDEX   (*(s16 *)(GAME + 8 + 0x13CC))
#define STAGE_CYCLE(s) (*(int *)(GAME + 8 + 0x28 + 4 * (s)))
#define BONUS_BASE    (*(u8 **)(GAME + 0xC7E4))
#define BONUS_STAGES  14
#define STAGE_SIZE    0x168

#define ENEMIES       0xB34
#define ENEMY_SIZE    20
#define ENEMY_COUNT   64
#define MAX_DROPS     20

static void put16(u8 *p, int v)
{
    p[0] = (u8)v;
    p[1] = (u8)(v >> 8);
}

int Loot_ScouterInfo(void *que, int channel, u8 *out)
{
    u8 *block;
    int stage, step, i, k, count;

    GetScouterInfo(que, channel, out);
    block = out + 0x200;
    for (i = 0; i < 0x80; i++)
        block[i] = 0;
    block[0] = 'L';
    block[1] = 'T';

    stage = STAGE_INDEX;
    block[3] = (u8)stage;
    if (stage >= 0 && stage < BONUS_STAGES && BONUS_BASE) {
        const u8 *rec = BONUS_BASE + STAGE_SIZE * stage;
        step = STAGE_CYCLE(stage);
        if (step > 2)
            step = 2;
        if (step < 0)
            step = 0;
        block[2] = (u8)step;
        for (i = 0; i < 4; i++)
            put16(block + 4 + 2 * i, *(const u16 *)(rec + 0x160 + 2 * i));
        for (i = 0; i < 16; i++)
            put16(block + 12 + 2 * i, *(const u16 *)(rec + 0x20 + 8 * (2 * step) + 2 * i));
    } else {
        block[2] = 0xFF;
    }

    count = 0;
    for (i = 0; i < ENEMY_COUNT && count < MAX_DROPS; i++) {
        const u8 *e = (const u8 *)que + ENEMIES + ENEMY_SIZE * i;
        if (e[3] == 0 || *(const u16 *)(e + 4) == 0)
            continue;
        for (k = 0; k < 4 && count < MAX_DROPS; k++) {
            int item = *(const s16 *)(e + 12 + 2 * k);
            if (item >= 0x9F && item <= 0xFF) {
                put16(block + 46 + 4 * count, item);
                block[46 + 4 * count + 2] = e[3];
                count++;
            }
        }
    }
    block[44] = (u8)count;
    return 0x280;
}
