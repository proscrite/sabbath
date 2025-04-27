from pylablib.devices.Thorlabs import KinesisMotor
# This is a Thorlabs Kinesis motor driver for a stage with serial number 26002227

# stage = KinesisMotor("26002227") # scale is in steps (So up to 2184533.33 steps/mm)
# stage = KinesisMotor("26002227", scale='ZFS25B')  # if the stage model is specified, the scale is in m/step (not very practical)
stage = KinesisMotor("26002227", scale=2184533.33) # scale is in mm/step
print(stage.get_position())  # get the current position in mm
stage.home(force=True) # home the stage (force=True to ignore currently homed status)
stage.move_by(1)  # move by 1 mm
stage.wait_move()  # wait for the move to finish
print(stage.get_position())  # get the current position in mm
stage.move_to(5)  # move to 5 mm absolute position
stage.wait_move()  # wait for the move to finish
print(stage.get_position())  