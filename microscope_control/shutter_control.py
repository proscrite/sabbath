import serial
arduino = serial.Serial("COM6", 9600, timeout=1) # Open serial port to arduino

def send_ttl(command):
        arduino.write(command.encode())  # Send 'H' (high), 'L' (low), or 'T' (toggle) 
        response = arduino.readline().decode().strip()
        print("Arduino says:", response)

def toggle_shutter():
    """Toggle the shutter on and off."""
    send_ttl('T')

def open_shutter():
    send_ttl('H')
    
def close_shutter():
    send_ttl('L') 

def __main__():
    while True:
        command = input("Enter command (T for toggle, H for open, L for close, Q to quit): ").strip().upper()
        command = command.lower()
        if command == 't':
            toggle_shutter()
        elif command == 'h':
            open_shutter()
        elif command == 'l':
            close_shutter()
        elif command == 'q':
            break
        else:
            print("Invalid command. Please enter T, H, L, or Q.")
    
if __name__ == "__main__":
    __main__()
    arduino.close()  # Close the serial port when done


    