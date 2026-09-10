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
track           .eq $304
bits            .eq $3c

sector          .eq $3d
data_ptr        .eq $26

LOCRPL      .eq $3e3
RWTS            .eq $3d9

sectors         .eq     $1500
tracks          .eq     $1600
volumes         .eq     $1700

NUM_SECTORS     .eq     32

start:
    .org $1000
    lda #34
    sta track

.trackstart:
    jsr LOCRPL
    sty LOC0
    sta LOC0+1

    ldy #1
    lda (LOC0),y        ; Slot number
    tax
    ldy #4
    lda track
    sta (LOC0),y        ; Track number
    lda IWM_MOTOR_ON,x

    lda LOC0+1
    ldy LOC0
    jsr RWTS

    lda IWM_MOTOR_ON,x
    lda #NUM_SECTORS
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
    sec
    rol
    sta bits

.readHead2
    lda IWM_Q6_OFF,x
    bpl .readHead2
    and bits
    dey
    sta SECT,y
    bne .readHead1

    ldy repeats
    lda SECT
    sta sectors,y
    lda TRK
    sta tracks,y
    lda VOL
    sta volumes,y

    dec repeats
    bne .read1

    ; Print the track's data
    ; Print the header
    lda #found_msg>>8
    sta LOC0 + 1
    lda #found_msg & $ff
    sta LOC0
    jsr Print
    lda track
    jsr PRBYTE
    lda #$D
    jsr COUT

    ldy #NUM_SECTORS
.print_data
    lda volumes,y
    jsr PRBYTE
    lda #" "
    jsr COUT
    lda tracks,y
    jsr PRBYTE
    lda #" "
    jsr COUT
    lda sectors,y
    jsr PRBYTE
    lda #$D
    jsr COUT

    dey
    bne .print_data

    ; Next track
    dec track
    bmi .finished
    jmp .trackstart

.finished
    lda IWM_MOTOR_OFF,x

    lda #0
    sta $48

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
found_msg:  .db "V,T,S: FOR TRACK ", 0
