import unittest
from services.simulator_api.design.sequence_projection import project_interval
class ProjectionTests(unittest.TestCase):
 def test_left_and_right_slices_share_forward_coordinate_system(self):
  seq='AUGCUAGC'; value=project_interval(seq,2,6)
  self.assertEqual(value['sense_5to3'],'GCUA')
  self.assertEqual(value['antisense_5to3'],'UAGC')
  self.assertEqual(value['antisense_coordinates'],[2,6])
 def test_invalid_interval_is_rejected(self):
  with self.assertRaises(ValueError): project_interval('AUG',0,4)
if __name__=='__main__': unittest.main()
import unittest
from services.simulator_api.design.sequence_projection import annotate_trajectory
class ProjectionTrajectoryTests(unittest.TestCase):
 def test_cut_and_remainder_sequences_are_added_without_changing_events(self):
  base={'config':{'construct':{'length_nt':8}},'events':[{'kind':'cut','start':0,'end':3,'cut_index':1},{'kind':'terminal','start':3,'end':8}], 'remainder':{'start':3,'end':8,'length_nt':5}}
  value=annotate_trajectory(base,'AUGCUAGC')
  self.assertEqual(value['events'][0]['cut_index'],1)
  self.assertEqual(value['events'][0]['sequence']['sense_5to3'],'AUG')
  self.assertEqual(value['events'][0]['sequence']['antisense_5to3'],'CAU')
  self.assertEqual(value['remainder']['sequence']['sense_5to3'],'CUAGC')
if __name__=='__main__':unittest.main()
