import asyncio

# Dictionary to store active connections (i.e., Discord bots)
active_connections = []

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"New connection from {addr}")
    
    active_connections.append((reader, writer))

    try:
        while True:
            # Receive data from the client (i.e., from a Discord bot)
            data = await reader.read(100)
            if not data:
                break
            
            message = data.decode()
            print(f"Received message: {message}")

            # Broadcast the message to all active connections
            for conn_reader, conn_writer in active_connections:
                if conn_writer != writer:  # Avoid sending the message back to the sender
                    try:
                        conn_writer.write(message.encode())
                        await conn_writer.drain()
                    except Exception as e:
                        print(f"Error sending message: {e}")
                        active_connections.remove((conn_reader, conn_writer))
                        conn_writer.close()
                        await conn_writer.wait_closed()

    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    
    finally:
        print(f"Closing connection with {addr}")
        active_connections.remove((reader, writer))
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    async with server:
        await server.serve_forever()

# Start the server
asyncio.run(main())
