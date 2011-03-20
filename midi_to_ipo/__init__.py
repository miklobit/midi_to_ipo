"""

Features:
* Handle as Drum 
* * Requires set of Drum Note to listen to
* * Will only insert keyframe is Drum Note has Note On or Note Off
* Reset on Note Off (Bool)
* * if true will insert a keyframe of the orginial position of the target on each note off
* Multiplier
* Animate by either Velocity or Key (Pitch)
* Handle (Additive or Set)
* * Additive will always move the target further on each Note On Event
* * Set will always move it according to its original position

 

 
"""

bl_addon_info = {
    "name": "Midi Driver",
    "author": "Kai Wegner",
    "version": (0, 1),
    "blender": (2, 5, 3),
    "api": 31667,
    "location": "Object ",
    "description": "Import Midi Events to Ipo Curves. Inspired and widely ported by the original Import midi drum part into IPO Script by Jean-Baptiste PERIN",
    "warning": "",
    "category": "Import-Export"}

import bpy
import sys

from . import Midi
registered_notes = []
def register_note(itrack_index, ichannel_index, ipitch, ivelocity,ikeyDownTime, ikeyUpTime):
    registered_notes.append({
                             "track":itrack_index, 
                             "chan":ichannel_index, 
                             "pitch":ipitch, 
                             "vel":ivelocity,
                             "keyDown":ikeyDownTime, 
                             "duration":ikeyUpTime-ikeyDownTime,
                             
                             "keyUp":ikeyUpTime})

class Midi_Generator(bpy.types.Operator):
    bl_idname="Midi_Generator"
    bl_label="Midi Generator"
    notes = ["c","d","e","f","g","a","h" ]
    object = None
    file = None
    MICROSECONDS_PER_MINUTE = 60000000
    tempo = TPQN = fps = 0
    bpm = 120
    track = None
    @classmethod
    def poll(cls, context):
        return context.object is not None


    def invoke(self, context, event):
        self.object = bpy.context.active_object
        
        self.cleanup()
        
        file = Midi.MidiFile()
        file.open(self.object.midi_setting_file)
        
        if self.object.midi_setting_asDrum:
            self.object.midi_setting_drum_inote = self.noteStringToInt(self.object.midi_setting_drum_note)
            print("drum listening to " + str(self.object.midi_setting_drum_inote))
        
        Midi.register_note = register_note
        
        file.read()
        
        self.framebase = context.scene.frame_start
        self.fps = context.scene.render.fps
        self.TPQN = file.ticksPerQuarterNote
        
        print("Framebase is at " + str(self.framebase))
        tracknum = self.object.midi_setting_track-1;   
        print ("execution")
        
        if(len(file.tracks) < tracknum):
            print ("Track not found")
        
        track = file.tracks[tracknum]
        
        
        print ("ticksPerQuarterNote = ", file.ticksPerQuarterNote," ticksPerSecond= ",file.ticksPerSecond)

        recent_pitch = 0
        org = [self.object.location.x,self.object.location.y,self.object.location.z]
        recent_location = org[:]
        
        print(self.object.midi_setting_multiplier)
        print(self.object.midi_setting_value,self.object.midi_setting_style)
        
        """ FIXME
         atm this spams the action editor with actions :-(
        """
        if(not self.object.animation_data):
            self.object.animation_data_create()
        
        if(not self.object.animation_data.action):
            self.object.animation_data.action = bpy.data.actions.new(name="Midi")
        
        fcux = self.object.animation_data.action.fcurves.new(data_path="location",array_index=0)
        fcuy = self.object.animation_data.action.fcurves.new(data_path="location",array_index=1)
        
        for ev in track.events:
            
            if(ev.type == "SET_TEMPO"):
                self.bpm = self.MICROSECONDS_PER_MINUTE / Midi.getNumber(ev.data, 3)[0]
                continue
                
            if(ev.type == "NOTE_OFF"):
                if(self.shouldSkipIfDrum(ev.pitch)):
                    continue
                self.object.location = org 
                print("Inserting Note Off")
                self.object.keyframe_insert(data_path="location", frame=self.getTimeFrame(ev.time))
            
            if(ev.type == "NOTE_ON"):
                
                if(self.shouldSkipIfDrum(ev.pitch)):
                    continue
                print("2",org[0],recent_location[0])

                if self.object.midi_setting_style == "ADD":
                    print("Reset Position")
                    org = recent_location[:]
                        
                # shall we animate velocity?
                if self.object.midi_setting_value == "VELOCITY" or self.object.midi_setting_value == "BOTH":
                    if ev.velocity > 0:
                        recent_location[0] = ev.velocity / 127 * self.object.midi_setting_multiplier + org[0] 
                    else:
                        recent_location[0] = org[0]
                        
                        print ("Had zero")
                print("3",org[0],recent_location[0])

                        
                # shall we animate key
                if self.object.midi_setting_value == "KEY" or self.object.midi_setting_value == "BOTH":
                    if ev.pitch is not recent_pitch:
                        recent_location[1] = org[1] + ev.pitch / 127 * self.object.midi_setting_multiplier
                        recent_pitch = ev.pitch 
                    else:
                        recent_location[1] = org[1]
                

                if(self.object.midi_setting_reset_on_note_off or ev.velocity > 0):
                    #self.object.location[0] = recent_location[0]
                    #self.object.location[1] = recent_location[1]
                    #self.object.keyframe_insert(data_path="location", frame=self.getTimeFrame(ev.time))
                    kfx = fcux.keyframe_points.add(value=recent_location[0],frame=self.getTimeFrame(ev.time))
                    kfx.interpolation = self.object.midi_setting_interpolation
                    kfy = fcuy.keyframe_points.add(value=recent_location[1],frame=self.getTimeFrame(ev.time))
                    kfy.interpolation = self.object.midi_setting_interpolation
        
                
                
        return {'RUNNING_MODAL'}
    
    def cleanup(self):
        if(self.object.midi_setting_clean):
            self.object.animation_data_clear()
    def getBeat(self,value):
        return value/ self.TPQN
    def getTimeFrame(self,value):
        # 840
        # bpm = 95
        # tpqn = 480
        # fps = 24
        # assume int are milliseconds
        return (value / self.TPQN /self.bpm * 60 * self.fps) + self.framebase
        
        
    
    def insertIpo(self,event):
        framebase = bpy.context.scene.frame_start
        #if(event.type == "NOTE_ON"):
        t = self.getTimeFrame(event.time)
            
        self.object.keyframe_insert(data_path="location", frame=t+framebase)
            
            
    def noteStringToInt(self,note):
        #Note
        n = str(note[0]).lower()
        #Octave
        o = 0
        #Sharp
        s = 0
        if note[1] == "#":
            s = 1
            o = int(note[2:])
        else:
            try:
                o = int(note[1:])
            except:
                return 0
            
        # we start with C1 at the third octave
        o = o + 2
        
        index = 0
        
        if n not in self.notes:
            return 0
        # converting string to int    
        for v in self.notes:
            if v == n:
                break;
            index = index + 2
        
        # adding sharpness
        index = index + s
            
        #handling octave
        index = index + o*12
        print(n,s,o)
        return index
    
    def shouldSkipIfDrum(self,pitch):
        #Never skip if we are no drum 
        if not self.object.midi_setting_asDrum:
            return False; 
        
        if pitch is self.object.midi_setting_drum_inote:
            return False
        
        return True
         


class Midi_File_Selector(bpy.types.Operator):
    bl_idname="Midi_File_Selector"
    
    bl_label = "Midi File Selector"
    
    filepath = bpy.props.StringProperty(subtype="FILE_PATH")
    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        object = bpy.context.active_object
        object.midi_setting_file = self.filepath
        
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_PT_Midi_Driver(bpy.types.Panel):
    bl_region_type = "WINDOW"
    bl_space_type = "PROPERTIES"
    bl_context = "object"
    bl_default_closed = False

    bl_label = "Midi_Driver"

    
    def draw(self, context):
        
        layout = self.layout
        object = bpy.context.active_object
        row = layout.row()
            
        if not object: 
            row.label(text="NO object selected...", icon='OBJECT_DATA')
            return
        
        row.operator(Midi_File_Selector.bl_idname,"Choose Midi File",icon='FILESEL')
        if object.midi_setting_file:
            row.prop(bpy.context.active_object, "midi_setting_file")
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_track")
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_asDrum")
            
            if bpy.context.active_object.midi_setting_asDrum == True:
                row = layout.row()
                row.prop(bpy.context.active_object, "midi_setting_drum_note")
        
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_interpolation")
            
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_clean")
            
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_reset_on_note_off")
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_multiplier")
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_value")
            row = layout.row()
            row.prop(bpy.context.active_object, "midi_setting_style")
            
            row = layout.row()
            row.operator(Midi_Generator.bl_idname, "Generate")
            
            
            
ipo_modes = [
                        ("BEZIER","Smooth",""),
                        ("LINEAR","Linear",""),
                        ("CONSTANT","Rectangle","")]
        
# Register all data we need
bpy.types.Object.midi_setting_file = bpy.props.StringProperty(
                                                             name="Midi File",
                                                             description="The Midi File to use data from",
                                                             )
bpy.types.Object.midi_setting_track = bpy.props.IntProperty(
                                                            name="Track",
                                                            description="The Track to animate from",
                                                            default=1,
                                                            min=1
                                                            )
bpy.types.Object.midi_setting_asDrum = bpy.props.BoolProperty(
                                                             name="Handle as Drum",
                                                             description="Driver will listen to specific note if this is selected")
bpy.types.Object.midi_setting_drum_note = bpy.props.StringProperty(
                                                             name="Drum Note",
                                                             description="Which Note of the Drum to listen to")
bpy.types.Object.midi_setting_drum_inote = bpy.props.IntProperty(
                                                             name="Drum Note in int",
                                                             description="Which Note of the Drum to listen to")
bpy.types.Object.midi_setting_interpolation = bpy.props.EnumProperty(items=ipo_modes,
                                                             name="Interpolation Mode",
                                                             description="How Ipos are created")
bpy.types.Object.midi_setting_clean = bpy.props.BoolProperty(name="Remove all other ipos",
                                                             description="If checked all other ipos will be removed on generation")
bpy.types.Object.midi_setting_reset_on_note_off = bpy.props.BoolProperty(name="Reset on Note Off",
                                                             description="When checked inserts a keyframe of the original position of the object if a Note OFF Event occurs",
                                                             default=True)
bpy.types.Object.midi_setting_multiplier = bpy.props.FloatProperty(name="Multiplier",
                                                             description="Value will be multiplied with this value",
                                                             default=1.0)
ipo_values = [
              ("VELOCITY","Velocity",""),
              ("KEY","Key",""),
              ("BOTH","Both","")
              ]
bpy.types.Object.midi_setting_value = bpy.props.EnumProperty(items=ipo_values,
                                                             name="Value to animate from",
                                                             description="The value to animate from. Velocity (0-127) (x axis), Key(0-127) (y axis)"
                                                             )

ipo_style = [
             ("ADD","Additive",""),
             ("SET","Set","")]
bpy.types.Object.midi_setting_style = bpy.props.EnumProperty(items=ipo_style,
                                                             name="Keyframe Style",
                                                             description="How to Add Keyframes"
                                                             )

def register():
    
    pass

def unregister():
    pass

if __name__ == "__main__":
    register()