form Cross Correlate two Sounds
  sentence Input_sound_1
  sentence Input_sound_2
  real duration 30.0
endform

Open long sound file... 'input_sound_1$'
Extract part: 0, duration, "no"
Extract one channel... 1
sound1 = selected("Sound")
Open long sound file... 'input_sound_2$'
Extract part: 0, duration, "no"
Extract one channel... 1
sound2 = selected("Sound")

select sound1
plus sound2
Cross-correlate: "peak 0.99", "zero"
offset = Get time of maximum: 0, 0, "Sinc70"

writeInfoLine: 'offset'

