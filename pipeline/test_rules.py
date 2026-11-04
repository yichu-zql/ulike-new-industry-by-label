import unittest
from classify import *
def row(title,b='鱼跃',cat='制氧机'):
 return {'item_name':title,'brand_name':b,'jq_cate3':cat,'plat':'jd','item_id':1,'y_m':202609}
class RulesTest(unittest.TestCase):
 def decision(self,title,b='鱼跃',cat='制氧机',d=None):return classify(row(title,b,cat),d or {})
 def test_home_oxygen(self):self.assertEqual(self.decision('家用医用分子筛制氧机')['status'],'included')
 def test_pro_system(self):self.assertEqual(self.decision('医用分子筛制氧系统专业人员操作')['status'],'excluded')
 def test_hospital_same_is_not_professional(self):self.assertEqual(self.decision('医院同款家用医用压缩式雾化器',cat='雾化器')['status'],'included')
 def test_hospital_only_conflict(self):self.assertEqual(self.decision('医院专用家用医用压缩式雾化器',cat='雾化器')['status'],'pending')
 def test_home_alone_not_medical(self):self.assertEqual(self.decision('家用制氧机')['status'],'pending')
 def test_medical_alone_not_molecular(self):self.assertEqual(self.decision('家用医用制氧机')['status'],'pending')
 def test_mesh_excluded(self):self.assertEqual(self.decision('家用医用网式雾化器',cat='雾化器')['status'],'excluded')
 def test_combination_not_system(self):self.assertEqual(self.decision('家用医用呼吸机与制氧机组合')['status'],'pending')
 def test_accessory(self):self.assertEqual(self.decision('制氧机配件分子筛颗粒')['status'],'excluded')
 def test_bundled_mask(self):self.assertEqual(self.decision('家用医用压缩式雾化器C900+2套雾化面罩',b='欧姆龙',cat='雾化器')['status'],'included')
 def test_ambiguous_accessory(self):self.assertEqual(self.decision('家用医用压缩式雾化器雾化面罩',cat='雾化器')['status'],'pending')
 def test_model_normalization(self):
  self.assertEqual(model_tokens('欧姆龙','NE-C900'),['C900'])
  self.assertEqual(model_tokens('鱼跃','403M'),['403M'])
  self.assertEqual(model_tokens('鱼跃','5L6L 8F-5AW'),['8F-5AW'])
 def test_model_evidence_brand_scoped(self):
  d=build_dictionary([row('家用医用分子筛制氧机8F-5AW')])
  self.assertEqual(self.decision('家用制氧机8F-5AW',d=d)['status'],'included')
  self.assertEqual(self.decision('家用制氧机8F-5AW',b='其他厂家',d=d)['status'],'pending')
 def test_unknown_brand(self):self.assertIsNone(brand('其他 Other'))
 def test_brand_alias(self):self.assertEqual(brand('欧姆龙 Omron'),brand('欧姆龙'))
if __name__=='__main__':unittest.main()
