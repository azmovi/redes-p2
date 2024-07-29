import asyncio
from tcputils import (
    FLAGS_SYN,
    FLAGS_ACK,
    read_header,
    calc_checksum,
    fix_checksum,
    make_header,
    MSS
)


class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        (
            src_port,
            dst_port,
            seq_no,
            ack_no,
            flags,
            window_size,
            checksum,
            urg_ptr,
        ) = read_header(segment)

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return
        if (
            not self.rede.ignore_checksum
            and calc_checksum(segment, src_addr, dst_addr) != 0
        ):
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4 * (flags >> 12) :]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            conexao = self.conexoes[id_conexao] = Conexao(
                self, id_conexao, seq_no, ack_no
            )
            if self.callback:
                self.callback(conexao)

        elif id_conexao in self.conexoes:
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print(
                '%s:%d -> %s:%d (pacote associado a conexão desconhecida)'
                % (src_addr, src_port, dst_addr, dst_port)
            )


class Conexao:
    def __init__(self, servidor, id_conexao, seq_no, ack_no):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.timer = asyncio.get_event_loop().call_later(
            1, self._exemplo_timer
        )
        self.seq_no = seq_no
        self.ack_no = ack_no
        self.handshake()
        # self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida

    def handshake(self):
        self.ack_no = self.seq_no + 1
        flags = FLAGS_SYN + FLAGS_ACK
        self._enviar(flags)

    def _enviar(self, flags):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        segmento = fix_checksum(
            make_header(dst_port, src_port, self.seq_no, self.ack_no, flags),
            src_addr,
            dst_addr,
        )
        self.servidor.rede.enviar(segmento, src_addr)

    def _exemplo_timer(self):
        print('Este é um exemplo de como fazer um timer')

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        if seq_no != self.ack_no:
            return
        self.ack_no = seq_no + len(payload)
        self.seq_no = ack_no
        if payload:
            flags = FLAGS_ACK
            self.callback(self, payload)
            self._enviar(flags)
            print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados):
        """
        Usado pela camada de aplicação para enviar dados
        """
        flags = FLAGS_ACK
        for i in range(0, len(dados), MSS):
            payload = dados[i: i + MSS]
            if payload:
                src_addr, src_port, dst_addr, dst_port = self.id_conexao
                segmento = fix_checksum(
                    make_header(dst_port, src_port, self.seq_no, self.ack_no, flags)
                    + payload,
                    src_addr,
                    dst_addr,
                )
                self.servidor.rede.enviar(segmento, src_addr)
                self.seq_no += len(payload)

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        # TODO: implemente aqui o fechamento de conexão
        pass
