OUTPUT_FORMAT("elf32-littlearm", "elf32-littlearm", "elf32-littlearm")
OUTPUT_ARCH(arm)
ENTRY(_start)

SECTIONS
{
    /* Adresse d'entrée standard des payloads relocalisés par Hekate en IRAM */
    . = 0x40010000;

    .text : ALIGN(16)
    {
        KEEP(*(.text._start))
        *(.text*)
        *(.rodata*)
        . = ALIGN(16);
    }

    /DISCARD/ :
    {
        *(.ARM.exidx*)
        *(.ARM.extab*)
        *(.ARM.attributes*)
        *(.comment*)
        *(.note*)
    }
}
