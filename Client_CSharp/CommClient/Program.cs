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
            string svr_ip = "127.0.0.1";
            int svr_port = 2021;

            if (args.Length >= 1)
            {
                svr_ip = args[0];
            }
            if (args.Length >= 2)
            {
                svr_port = Int32.Parse(args[1]);
            }

            ClientConn conn = new ClientConn(svr_ip, svr_port, Program.OnCommingData);
            if (0 != conn.Start())
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
                    conn.Stop();
                    break;
                }
                else if (in_str.Length > 0)
                {
                    Console.WriteLine("Send to other clients: [{0}]", in_str);
                    conn.SendData(in_str);
                }
            }
            Console.WriteLine("Done!");
        }

        public static int OnCommingData(string data)
        {
            Console.WriteLine("Recieved data from other client: [{0}]", data);
            return 0;
        }
    }
}