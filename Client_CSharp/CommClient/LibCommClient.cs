using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json;

namespace LibCommClient
{
    public class TPTcpPdu
    {
        public string action { get; set; }
        public string data { get; set; }
    }

    class TcpConnnection
    {
        private const int PACKET_LIMIT = 1024 * 1024;
        private const int HEADER_LEN = 4;
        private Socket socket_client = null;
        private string svr_ip;
        private int svr_port;
        private Func<byte[], int> recv_cb;
        private Thread recvThread = null;
        private bool runningReceiving = true;

        public TcpConnnection(string svr_ip, int svr_port, Func<byte[], int> recv_cb)
        {
            this.svr_ip = svr_ip;
            this.svr_port = svr_port;
            this.recv_cb = recv_cb;
        }

        public int Start()
        {
            Console.WriteLine("TCP Connect to server at {0}:{1}", svr_ip, svr_port);
            socket_client = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            try
            {
                socket_client.Connect(svr_ip, svr_port);
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return -1;
            }

            recvThread = new Thread(new ThreadStart(ReceiveDataThreadProc));
            recvThread.Start();
            return 0;
        }

        public void ReceiveDataThreadProc()
        {
            while (runningReceiving)
            {
                byte[] client_pdu = RecvData();
                if (client_pdu == null)
                {
                    break;
                }
                if (client_pdu.Length == 0)
                {
                    continue;
                }
                recv_cb(client_pdu);
            }
        }

        public bool IsClosed()
        {
            return socket_client == null;
        }

        public void Stop()
        {
            if (recvThread != null && recvThread.IsAlive)
            {
                runningReceiving = false;
                recvThread.Join();
            }
            socket_client.Shutdown(SocketShutdown.Both);
            socket_client.Close();
            socket_client = null;
        }

        public int SendData(byte[] data)
        {
            int len = data.Length;
            if (len <= 0)
            {
                return 0;
            }
            if (len > PACKET_LIMIT)
            {
                len = PACKET_LIMIT;
            }
            byte[] bytes_hdr = BitConverter.GetBytes(len);
            byte[] buffer = new byte[HEADER_LEN + len];
            Array.Copy(bytes_hdr, buffer, HEADER_LEN);
            Array.Copy(data, 0, buffer, HEADER_LEN, len);
            socket_client.Send(buffer);
            return buffer.Length;
        }

        public byte[] RecvData()
        {
            byte[] bytes_hdr = new byte[HEADER_LEN];
            try
            {
                if (socket_client.Poll(1000, SelectMode.SelectRead))
                {
                    int byteCount = socket_client.Receive(bytes_hdr, HEADER_LEN, SocketFlags.None);
                    if (byteCount == 0)
                    {
                        Console.WriteLine("Socket closed by peer");
                        return null;
                    }
                }
                else
                {
                    return new byte[] { };
                }
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return null;
            }
            int data_len = BitConverter.ToInt32(bytes_hdr, 0);
            if (data_len <= 0)
            {
                Console.WriteLine("incorrect length, {0} bytes parsed from header block", data_len);
                return null;
            }
            byte[] bytes_data = new byte[data_len];
            try
            {
                int byteCount = socket_client.Receive(bytes_data, data_len, SocketFlags.None);
                if (byteCount == 0 || byteCount < data_len)
                {
                    Console.WriteLine("Received {0} bytes, Socket closed by peer", byteCount);
                    return null;
                }
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return null;
            }
            return bytes_data;
        }
    }

    class UdpConnnection
    {
        private const int PACKET_LIMIT = 1024;
        private Socket socket_client = null;
        private string svr_ip;
        private int svr_port;
        private Func<byte[], int> recv_cb;
        private Thread recvThread = null;
        private bool runningReceiving = true;

        public UdpConnnection(string svr_ip, int svr_port, Func<byte[], int> recv_cb)
        {
            this.svr_ip = svr_ip;
            this.svr_port = svr_port;
            this.recv_cb = recv_cb;
        }

        public int Start()
        {
            Console.WriteLine("UDP Connect to server at {0}:{1}", svr_ip, svr_port);
            socket_client = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            try
            {
                socket_client.Connect(svr_ip, svr_port);
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return -1;
            }
            this.SendData(Encoding.ASCII.GetBytes("010011000111"));
            recvThread = new Thread(new ThreadStart(ReceiveDataThreadProc));
            recvThread.Start();
            return 0;
        }

        public void ReceiveDataThreadProc()
        {
            while (runningReceiving)
            {
                byte[] client_pdu = RecvData();
                if (client_pdu == null)
                {
                    break;
                }
                if (client_pdu.Length == 0)
                {
                    continue;
                }
                recv_cb(client_pdu);
            }
        }

        public bool IsClosed()
        {
            return socket_client == null;
        }

        public void Stop()
        {
            if (recvThread != null && recvThread.IsAlive)
            {
                runningReceiving = false;
                recvThread.Join();
            }
            socket_client.Shutdown(SocketShutdown.Both);
            socket_client.Close();
            socket_client = null;
        }

        public int SendData(byte[] data)
        {
            if (data.Length <= 0)
            {
                return 0;
            }
            byte[] bytes_data = null;
            if (data.Length > PACKET_LIMIT)
            {
                bytes_data = new byte[PACKET_LIMIT];
                Array.Copy(data, bytes_data, PACKET_LIMIT);
            }
            else
            {
                bytes_data = data;
            }
            socket_client.Send(bytes_data);
            return bytes_data.Length;
        }

        public byte[] RecvData()
        {
            byte[] bytes_data = new byte[PACKET_LIMIT];
            try
            {
                if (socket_client.Poll(1000, SelectMode.SelectRead))
                {
                    int byteCount = socket_client.Receive(bytes_data, PACKET_LIMIT, SocketFlags.None);
                    if (byteCount == 0)
                    {
                        Console.WriteLine("Socket closed by peer");
                        return null;
                    }
                    byte[] bytes_received = new byte[byteCount];
                    Array.Copy(bytes_data, bytes_received, byteCount);
                    return bytes_received;
                }
                else
                {
                    return new byte[] { };
                }
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return null;
            }
        }
    }

    class Transport
    {
        private string svr_ip;
        private int svr_port;
        private Func<byte[], int> tcp_recv_cb;
        private Func<byte[], int> udp_recv_cb;
        private TcpConnnection tcp_conn = null;
        private UdpConnnection udp_conn = null;

        public Transport(string svr_ip, int svr_port, Func<byte[], int> tcp_recv_cb, Func<byte[], int> udp_recv_cb)
        {
            this.svr_ip = svr_ip;
            this.svr_port = svr_port;
            this.tcp_recv_cb = tcp_recv_cb;
            this.udp_recv_cb = udp_recv_cb;
        }

        public int Connect()
        {
            Console.WriteLine("Connect to communication server at {0}:{1}", svr_ip, svr_port);
            tcp_conn = new TcpConnnection(svr_ip, svr_port, OnTcpDataReceived);
            return tcp_conn.Start();
        }

        public int OnTcpDataReceived(byte[] data)
        {
            TPTcpPdu pdu = JsonConvert.DeserializeObject<TPTcpPdu>(Encoding.Default.GetString(data));
            if (pdu.action == "create_udp_channel")
            {
                int udp_port = Int32.Parse(pdu.data);
                udp_conn = new UdpConnnection(svr_ip, udp_port, OnUdpDataReceived);
                udp_conn.Start();
            } else
            {
                tcp_recv_cb(data);
            }

            return 0;
        }

        public int OnUdpDataReceived(byte[] data)
        {
            udp_recv_cb(data);
            return 0;
        }

        public void SendTcpPdu(string action, string data_str)
        {
            TPTcpPdu pdu = new TPTcpPdu();
            pdu.action = action;
            pdu.data = data_str;
            string cmd_str = JsonConvert.SerializeObject(pdu);
            tcp_conn.SendData(Encoding.ASCII.GetBytes(cmd_str));
        }

        public void CreateUdpChannel()
        {
            SendTcpPdu("create_udp_channel", "");
        }

        public void SendTcpData(string data_str)
        {
            SendTcpPdu("data", data_str);
        }

        public void BroadcastTcpMessage(string msg_str)
        {
            SendTcpPdu("broadcast", msg_str);
        }

        public void SendUdpData(byte[] data)
        {
            if (udp_conn == null)
                return;
            udp_conn.SendData(data);
        }

        public bool IsClosed()
        {
            return tcp_conn == null;
        }

        public void Close()
        {
            if (tcp_conn != null)
            {
                tcp_conn.Stop();
                tcp_conn = null;
            }
            if (udp_conn != null)
            {
                udp_conn.Stop();
                udp_conn = null;
            }
        }
    }
}