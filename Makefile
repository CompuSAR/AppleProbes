ASM=../vasm/vasm6502_oldstyle

all: sector_order.lst

%.lst: %.s
	$(ASM) -x -dotdir $(CPU_OPTIONS) -dependall=make -depfile "$*.dep" -L "$*.lst" "$<" -o "$*.out"
	sed -i -e 's/$*\.bin/\0 $*.lst/' "$*.dep"

