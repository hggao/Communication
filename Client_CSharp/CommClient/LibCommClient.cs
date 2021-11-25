using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace LibCommClient
{
    class ClientConn
    {
        private const int PACKET_LIMIT = 1024 * 1024;
        private Socket socket_client = null;
        private string svr_ip;
        private int svr_port;
        private Func<string, int> recv_cb;
        private Thread recvThread = null;
        private bool runningReceiving = true;

        public ClientConn(string svr_ip, int svr_port, Func<string, int> recv_cb)
        {
            this.svr_ip = svr_ip;
            this.svr_port = svr_port;
            this.recv_cb = recv_cb;
        }

        public int Start()
        {
            Console.WriteLine("Connect to communication server at {0}:{1}", svr_ip, svr_port);
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

            recvThread = new Thread(new ThreadStart(IncommingDataReceivingThread));
            recvThread.Start();
            return 0;
        }

        public void IncommingDataReceivingThread()
        {
            while (runningReceiving)
            {
                string client_pdu = RecvData();
                if (client_pdu == null)
                {
                    break;
                }
                if (client_pdu == "")
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

        public int SendData(string data_str)
        {
            if (data_str.Length <= 0)
            {
                return 0;
            }
            if (data_str.Length > PACKET_LIMIT)
            {
                data_str = data_str.Substring(0, PACKET_LIMIT);
            }
            byte[] bytes_data = Encoding.ASCII.GetBytes(data_str);

            string head_str = String.Format("{0, 12}", bytes_data.Length);
            byte[] bytes_hdr = Encoding.ASCII.GetBytes(head_str);
            socket_client.Send(bytes_hdr);
            socket_client.Send(bytes_data);
            return bytes_hdr.Length + bytes_data.Length;
        }

        public string RecvData()
        {
            byte[] bytes_hdr = new byte[12];
            byte[] bytes_data = null;
            try
            {
                if (socket_client.Poll(1000, SelectMode.SelectRead))
                {
                    int byteCount = socket_client.Receive(bytes_hdr, 12, SocketFlags.None);
                    if (byteCount == 0)
                    {
                        Console.WriteLine("Socket closed by peer");
                        return null;
                    }
                }
                else
                {
                    return "";
                }
            }
            catch (SocketException e)
            {
                Console.WriteLine("{0} Error code: {1}.", e.Message, e.ErrorCode);
                return null;
            }
            int data_len = Int32.Parse(Encoding.Default.GetString(bytes_hdr));
            if (data_len <= 0)
            {
                Console.WriteLine("incorrect length, {0} bytes parsed from header block", data_len);
                return null;
            }
            bytes_data = new byte[data_len];
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
            return Encoding.Default.GetString(bytes_data);
        }
    }
}