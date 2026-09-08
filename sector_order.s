IWM_MOTOR_OFF   .eq     $c088           ;stop drive spinning
IWM_MOTOR_ON    .eq     $c089           ;starts drive spinning
IWM_SEL_DRIVE_1 .eq     $c08a           ;selects drive 1
IWM_Q6_OFF      .eq     $c08c           ;read
IWM_Q7_OFF      .eq     $c08e           ;WP sense/read

LOC0            .eq     $00
LOC1            .eq     $01
PRBYTE          .eq     $FDDA           ; ROM print byte in A in HEX
COUT            .eq     $FDED           ; Print char in A

SECT            .eq $300
TRK             .eq $301
VOL             .eq $302
repeats         .eq $303
bits            .eq $3c

sector          .eq $3d
data_ptr        .eq $26

start:
    .org $1000
    ldx #$60
    lda IWM_SEL_DRIVE_1,x
    lda IWM_MOTOR_ON,x

    lda #32
    sta repeats

    sec

.read1
    lda IWM_Q6_OFF,x
    bpl .read1
    cmp #$d5
    bne .read1

.read2
    lda IWM_Q6_OFF,x
    bpl .read2
    cmp #$aa
    bne .read1

.read3
    lda IWM_Q6_OFF,x
    bpl .read3
    cmp #$96
    bne .read1

    ldy #3
.readHead1
    lda IWM_Q6_OFF,x
    bpl .readHead1
    rol
    sta bits

.readHead2
    lda IWM_Q6_OFF,x
    bpl .readHead2
    and bits
    dey
    sta SECT,y
    bne .readHead1

    ; Read the header
    lda #found_msg>>8
    sta LOC0 + 1
    lda #found_msg & $ff
    sta LOC0
    jsr Print

    lda VOL
    jsr PRBYTE
    lda #" "
    jsr COUT
    lda TRK
    jsr PRBYTE
    lda #" "
    jsr COUT
    LDA SECT
    jsr PRBYTE
    lda #13
    jsr COUT

    dec repeats
    bne .read1

    lda IWM_MOTOR_OFF,x

    rts

Print:
    ldy #0
    jmp .enter
.out
    jsr COUT
    iny
.enter
    lda (LOC0),y
    bne .out
    rts
found_msg:  .db "LOCATED V,T,S: ", 0
