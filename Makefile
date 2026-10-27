PREFIX  ?= arm-none-eabi-
AS      := $(PREFIX)as
LD      := $(PREFIX)ld
OBJCOPY := $(PREFIX)objcopy
OBJDUMP := $(PREFIX)objdump

TARGET  := reboot_ofw.bin
ELF     := reboot_ofw.elf
OBJ     := reboot.o

ASFLAGS := -march=armv4t -mcpu=arm7tdmi
LDFLAGS := -T linker.ld --nmagic

.PHONY: all clean dump

all: $(TARGET)

$(OBJ): reboot.s
	$(AS) $(ASFLAGS) $< -o $@

$(ELF): $(OBJ) linker.ld
	$(LD) $(LDFLAGS) $(OBJ) -o $@

$(TARGET): $(ELF)
	$(OBJCOPY) -S -O binary $< $@

dump: $(ELF)
	$(OBJDUMP) -d -s $<

clean:
	rm -f $(OBJ) $(ELF) $(TARGET)
