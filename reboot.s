/*
 * Micro-payload : reboot_ofw.bin
 * Cible         : Nintendo Switch (Tegra X1 T210 / T210B01 Mariko) - BPMP (ARM7TDMI / ARMv4T)
 * Adresse IRAM  : 0x40010000 (chargé via le relocator de Hekate)
 * Objectif      : Reproduire à l'identique la séquence matérielle "Reboot -> OFW" de Nyx
 *                 (power_set_state(REBOOT_BYPASS_FUSES) -> panic(PMC_NX_PANIC_BYPASS_FUSES))
 *                 avec repli de sécurité sur PMC_CNTRL_MAIN_RST.
 */

.section .text._start, "ax", %progbits
.arch armv4t
.arm
.align 4
.global _start
.type _start, %function

_start:
    /* 1. Charger l'adresse de base du Tegra Power Management Controller (PMC_BASE = 0x7000E400) */
    ldr r0, =0x7000E400

    /* 2. Nettoyer APBDEV_PMC_SCRATCH0 (offset 0x50) à 0 */
    /* Efface tout drapeau résiduel (RCM, bootloader, recovery, warmboot) */
    mov r1, #0
    str r1, [r0, #0x50]

    /* 3. Écrire PMC_NX_PANIC_BYPASS_FUSES (0x21) dans APBDEV_PMC_SCRATCH200 (offset 0x840) */
    /* Identique à panic(PMC_NX_PANIC_BYPASS_FUSES) dans Hekate : indique au Package1 */
    /* officiel de démarrer l'OFW proprement sans vérification/brûlage des e-fuses */
    mov r1, #0x21
    str r1, [r0, #0x840]

    /* 4. Déclencher le reset PMC immédiat via Watchdog 4 (watchdog_start(0, TIMER_PMCRESET_EN)) */
    /* Identique à la fonction panic() de Hekate (TMR_BASE = 0x60005000) */
    ldr r2, =0x60005000

    /* TMR(TIMER_WDT4_UNLOCK_PATTERN) = TIMER_MAGIC_PTRN (0xC45A à l'offset 0x18C) */
    ldr r3, =0x0000C45A
    str r3, [r2, #0x18C]

    /* TMR(TIMER_TMR9_TMR_PTV) = TIMER_EN | TIMER_PER_EN | 0 (0xC0000000 à l'offset 0x080) */
    mov r3, #0xC0000000
    str r3, [r2, #0x080]

    /* TMR(TIMER_WDT4_CONFIG) = TIMER_SRC(9) | TIMER_PER(1) | TIMER_PMCRESET_EN (0x8019 à l'offset 0x180) */
    ldr r3, =0x00008019
    str r3, [r2, #0x180]

    /* TMR(TIMER_WDT4_COMMAND) = TIMER_START_CNT (0x1 à l'offset 0x188) */
    mov r3, #1
    str r3, [r2, #0x188]

    /* 5. Boucle d'attente (~480 µs à 408 MHz) pour laisser WDT4 déclencher TIMER_PMCRESET_EN (~1 µs) */
    mov r3, #0x10000
wait_wdt:
    subs r3, r3, #1
    bne wait_wdt

    /* 6. Fallback de sécurité : si WDT4 n'a pas coupé le SoC, forcer MAIN_RST (bit 4 = 0x10) dans PMC_CNTRL */
    ldr r1, [r0, #0x00]
    orr r1, r1, #0x10
    str r1, [r0, #0x00]

hang:
    /* Boucle de rétention infinie en attendant la coupure matérielle du SoC */
    b hang

.ltorg
.balign 16, 0x00
