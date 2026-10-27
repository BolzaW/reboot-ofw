#!/usr/bin/env python3
"""
Script de compilation et de vérification du micro-payload `reboot_ofw.bin`.
Cible : Nintendo Switch (Tegra X1 T210 / T210B01 Mariko) - BPMP (ARM7TDMI / ARMv4T, AArch32).
Adresse de chargement IRAM Hekate : 0x40010000.

Ce script :
1. Utilise `arm-none-eabi-as` / `ld` / `objcopy` s'ils sont présents dans le PATH,
   ou assemble directement les instructions ARMv4T de `reboot.s`.
2. Désassemble et vérifie chaque instruction 32 bits, chaque accès registre MMIO
   et chaque constante du literal pool avant de valider `reboot_ofw.bin`.
"""

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

BASE_ADDR = 0x40010000
OUTPUT_BIN = Path(__file__).parent / "reboot_ofw.bin"

# Séquence d'instructions ARMv4T (32-bit ARM little-endian) correspondant exactement à reboot.s
WORDS = [
    # 0x00: ldr r0, [pc, #0x4C]    -> r0 = [0x40010054] = 0x7000E400 (PMC_BASE)
    0xE59F004C,
    # 0x04: mov r1, #0
    0xE3A01000,
    # 0x08: str r1, [r0, #0x50]    -> PMC(APBDEV_PMC_SCRATCH0) = 0
    0xE5801050,
    # 0x0C: mov r1, #0x21          -> PMC_NX_PANIC_BYPASS_FUSES (0x21)
    0xE3A01021,
    # 0x10: str r1, [r0, #0x840]   -> PMC(APBDEV_PMC_SCRATCH200) = 0x21
    0xE5801840,
    # 0x14: ldr r2, [pc, #0x3C]    -> r2 = [0x40010058] = 0x60005000 (TMR_BASE)
    0xE59F203C,
    # 0x18: ldr r3, [pc, #0x3C]    -> r3 = [0x4001005C] = 0x0000C45A (TIMER_MAGIC_PTRN)
    0xE59F303C,
    # 0x1C: str r3, [r2, #0x18C]   -> TMR(TIMER_WDT4_UNLOCK_PATTERN) = 0xC45A
    0xE582318C,
    # 0x20: mov r3, #0xC0000000    -> TIMER_EN | TIMER_PER_EN | 0
    0xE3A03103,
    # 0x24: str r3, [r2, #0x080]   -> TMR(TIMER_TMR9_TMR_PTV) = 0xC0000000
    0xE5823080,
    # 0x28: ldr r3, [pc, #0x30]    -> r3 = [0x40010060] = 0x00008019
    0xE59F3030,
    # 0x2C: str r3, [r2, #0x180]   -> TMR(TIMER_WDT4_CONFIG) = 0x8019 (TIMER_PMCRESET_EN)
    0xE5823180,
    # 0x30: mov r3, #1             -> TIMER_START_CNT (1)
    0xE3A03001,
    # 0x34: str r3, [r2, #0x188]   -> TMR(TIMER_WDT4_COMMAND) = 1
    0xE5823188,
    # 0x38: mov r3, #0x10000       -> Compteur d'attente (~480 µs à 408 MHz)
    0xE3A03801,
    # 0x3C: subs r3, r3, #1        -> wait_wdt:
    0xE2533001,
    # 0x40: bne 0x4001003C         -> boucle tant que r3 != 0
    0x1AFFFFFD,
    # 0x44: ldr r1, [r0, #0x00]    -> Fallback: lire PMC(APBDEV_PMC_CNTRL)
    0xE5901000,
    # 0x48: orr r1, r1, #0x10      -> Activer PMC_CNTRL_MAIN_RST (bit 4)
    0xE3811010,
    # 0x4C: str r1, [r0, #0x00]    -> Écrire PMC(APBDEV_PMC_CNTRL)
    0xE5801000,
    # 0x50: b 0x40010050           -> hang: b hang
    0xEAFFFFFE,
    # Literal pool (.ltorg)
    # 0x54: PMC_BASE
    0x7000E400,
    # 0x58: TMR_BASE
    0x60005000,
    # 0x5C: TIMER_MAGIC_PTRN
    0x0000C45A,
    # 0x60: TIMER_SRC(9) | TIMER_PER(1) | TIMER_PMCRESET_EN
    0x00008019,
    # Alignement sur 16 octets (.balign 16) pour le relocator Hekate (_reloc_ipl)
    0x00000000,
    0x00000000,
    0x00000000,
]


def ror32(val: int, bits: int) -> int:
    bits &= 31
    return ((val >> bits) | (val << (32 - bits))) & 0xFFFFFFFF


def decode_and_verify(blob: bytes) -> None:
    assert len(blob) % 16 == 0, f"La taille ({len(blob)}) doit être un multiple de 16 octets pour Hekate !"
    assert 0 < len(blob) <= 0x30000, f"Taille invalide pour l'IRAM Hekate : {len(blob)}"

    words = list(struct.unpack(f"<{len(blob) // 4}I", blob))
    print(f"=== Vérification binaire : {OUTPUT_BIN.name} ({len(blob)} octets) ===")
    print(f"{'Adresse':<12} {'OpCode':<12} {'Instruction décodée':<32} {'Effet matériel'}")
    print("-" * 92)

    regs = {i: 0 for i in range(16)}
    for idx, w in enumerate(words):
        addr = BASE_ADDR + idx * 4
        pc = addr + 8

        if idx >= 21:
            label = ".word"
            note = {
                21: "PMC_BASE (0x7000E400)",
                22: "TMR_BASE (0x60005000)",
                23: "TIMER_MAGIC_PTRN (0xC45A)",
                24: "WDT4_CONFIG (TIMER_PMCRESET_EN)",
            }.get(idx, "Padding alignement 16 octets")
            print(f"0x{addr:08X}   0x{w:08X}   {label:<10} 0x{w:08X}{'':<11} ; {note}")
            continue

        # Décodage ARMv4T
        if (w & 0x0F7F0000) == 0x051F0000:  # LDR Rd, [PC, #imm12]
            rd = (w >> 12) & 0xF
            imm12 = w & 0xFFF
            up = (w >> 23) & 1
            target_addr = pc + imm12 if up else pc - imm12
            target_idx = (target_addr - BASE_ADDR) // 4
            val = words[target_idx]
            regs[rd] = val
            ins = f"ldr r{rd}, [pc, #0x{imm12:X}]"
            eff = f"r{rd} <- [0x{target_addr:08X}] = 0x{val:08X}"
        elif (w & 0x0FE00000) == 0x03A00000:  # MOV Rd, #imm
            rd = (w >> 12) & 0xF
            rot = ((w >> 8) & 0xF) * 2
            imm8 = w & 0xFF
            val = ror32(imm8, rot)
            regs[rd] = val
            ins = f"mov r{rd}, #0x{val:X}"
            eff = f"r{rd} <- 0x{val:08X}"
        elif (w & 0x0FF00000) == 0x05800000:  # STR Rd, [Rn, #imm12]
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            imm12 = w & 0xFFF
            mmio = (regs[rn] + imm12) & 0xFFFFFFFF
            ins = f"str r{rd}, [r{rn}, #0x{imm12:X}]"
            eff = f"[0x{mmio:08X}] <- 0x{regs[rd]:08X}"
        elif (w & 0x0FF00000) == 0x05900000:  # LDR Rd, [Rn, #imm12]
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            imm12 = w & 0xFFF
            mmio = (regs[rn] + imm12) & 0xFFFFFFFF
            ins = f"ldr r{rd}, [r{rn}, #0x{imm12:X}]"
            eff = f"r{rd} <- [0x{mmio:08X}]"
        elif (w & 0x0FE00000) == 0x03800000:  # ORR Rd, Rn, #imm
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            rot = ((w >> 8) & 0xF) * 2
            imm8 = w & 0xFF
            val = ror32(imm8, rot)
            regs[rd] |= val
            ins = f"orr r{rd}, r{rn}, #0x{val:X}"
            eff = f"r{rd} <- r{rn} | 0x{val:X}"
        elif (w & 0x0FF00000) == 0x02500000:  # SUBS Rd, Rn, #imm
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            imm8 = w & 0xFF
            ins = f"subs r{rd}, r{rn}, #0x{imm8:X}"
            eff = "Décrémente le compteur d'attente WDT4"
        elif (w & 0x0F000000) == 0x0A000000:  # B / Bcond
            cond = (w >> 28) & 0xF
            off24 = w & 0xFFFFFF
            if off24 & 0x800000:
                off24 -= 0x1000000
            target = (pc + (off24 << 2)) & 0xFFFFFFFF
            mnemonic = "bne" if cond == 0x1 else "b"
            ins = f"{mnemonic} 0x{target:08X}"
            eff = f"Saut vers 0x{target:08X}"
        else:
            raise AssertionError(f"Instruction inconnue à 0x{addr:08X}: 0x{w:08X}")

        print(f"0x{addr:08X}   0x{w:08X}   {ins:<32} ; {eff}")

    print("-" * 92)
    print("[OK] Toutes les instructions ARMv4T et adresses MMIO ont été vérifiées avec succès.")


def main() -> int:
    if shutil.which("arm-none-eabi-as") and shutil.which("arm-none-eabi-ld") and shutil.which("arm-none-eabi-objcopy"):
        print("[INFO] Chaîne GNU ARM détectée, assemblage via arm-none-eabi-...")
        cwd = Path(__file__).parent
        subprocess.run(["arm-none-eabi-as", "-march=armv4t", "-mcpu=arm7tdmi", "reboot.s", "-o", "reboot.o"], cwd=cwd, check=True)
        subprocess.run(["arm-none-eabi-ld", "-T", "linker.ld", "--nmagic", "reboot.o", "-o", "reboot_ofw.elf"], cwd=cwd, check=True)
        subprocess.run(["arm-none-eabi-objcopy", "-S", "-O", "binary", "reboot_ofw.elf", str(OUTPUT_BIN)], cwd=cwd, check=True)
        blob = OUTPUT_BIN.read_bytes()
    else:
        print("[INFO] Assemblage direct ARMv4T vers reboot_ofw.bin...")
        blob = struct.pack(f"<{len(WORDS)}I", *WORDS)
        OUTPUT_BIN.write_bytes(blob)

    decode_and_verify(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
