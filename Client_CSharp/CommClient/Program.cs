using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using LibCommClient;

namespace CommClient
{
    class Program
    {
        static void Main(string[] args)
        {
            string svr_ip = "www.tenkmiles.com";
            int svr_port = 2021;

            if (args.Length >= 1)
            {
                svr_ip = args[0];
            }
            if (args.Length >= 2)
            {
                svr_port = Int32.Parse(args[1]);
            }

            Transport conn = new Transport(svr_ip, svr_port, Program.OnTcpDataReceived, Program.OnUdpDataReceived);
            if (0 != conn.Connect())
            {
                Console.WriteLine("Cannot start a connection to server, check if server is ready, or args are wrong.");
                return;
            }

            Console.WriteLine("Type 'quit' to quit or anything else as a message send to other clients");
            string in_str;
            while (true)
            {
                in_str = Console.ReadLine();
                if (conn.IsClosed())
                {
                    Console.WriteLine("Connection to server is closed, quit now.");
                    break;
                }
                if (in_str == "quit")
                {
                    Console.WriteLine("exit now......");
                    conn.Close();
                    break;
                }
                else if (in_str == "udp")
                {
                    conn.CreateUdpChannel();
                }
                else if (in_str.Length > 0)
                {
                    if (in_str.StartsWith("toudp:"))
                    {
                        Console.WriteLine("Send to UDP channel: [{0}]", in_str);
                        conn.SendUdpData(Encoding.ASCII.GetBytes(in_str));
                    } 
                    else if (in_str.StartsWith("totcp:"))
                    {
                        Console.WriteLine("Send to TCP channel for broadcast: [{0}]", in_str);
                        conn.BroadcastTcpMessage(in_str);
                    }
                    else
                    {
                        Console.WriteLine("Send to TCP channel: [{0}]", in_str);
                        conn.SendTcpData(in_str);
                    }
                }
            }
            Console.WriteLine("Done!");
        }

        public static int OnTcpDataReceived(byte[] data)
        {
            Console.WriteLine("Recieved tcp data: [{0}]", Encoding.Default.GetString(data));
            return 0;
        }

        public static int OnUdpDataReceived(byte[] data)
        {
            Console.WriteLine("Recieved udp data: [{0}]", Encoding.Default.GetString(data));
            return 0;
        }
    }
}