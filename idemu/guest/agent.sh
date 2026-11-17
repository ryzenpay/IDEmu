#!/bin/ksh
# IDEmu - agente de dados do guest: recebe do host (UART1 = /dev/ser5) o estado do CAN e do GPS virtuais.
#   C <ID-hex> <dados-hex>   ->  /var/idemu/can/<ID>      (último quadro de cada ID)
#   G <sentença NMEA>        ->  /var/idemu/gps/<TIPO>    (ex.: GPGGA, GPRMC)
#   X <comando>              ->  roda no shell do guest e devolve a saída ao host ("X <rc>|cmd", "X |linha"... até "X $") — /api/guest/exec
mkdir -p /var/idemu/can /var/idemu/gps
export PATH=/bin:/usr/bin:/bin/edge:/boot/bin:/opt/sys/bin LD_LIBRARY_PATH=/lib:/boot/lib:/opt/hmi/lib
devc-sernuke -N -u5 -E -F -b921600 -c48000000/13 0x4806A000^2,104 > /dev/null 2>&1 &
waitfor /dev/ser5 10
while read -r line; do
  t=${line%% *}
  case "$t" in
    C) set -- $line; echo "$3" > /var/idemu/can/$2 ;;
    G) s=${line#G }; s=${s#\$}; echo "${line#G }" > /var/idemu/gps/${s%%,*} ;;
    X) cmd=${line#X }; out=$(ksh -c "$cmd" 2>&1 </dev/null); rc=$?   # </dev/null: senão o comando herda o /dev/ser5 do agente e engole os próximos pedidos
       { echo "X $rc|$cmd"; echo "$out" | sed -n 1,150p | sed 's/^/X |/'; echo 'X $'; } > /dev/ser5 </dev/null ;;
  esac
done < /dev/ser5
