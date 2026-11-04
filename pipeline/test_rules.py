import unittest
from classify import *
def row(title,b='鱼跃',cat='制氧机'):
 return {'item_name':title,'brand_name':b,'jq_cate3':cat,'plat':'jd','item_id':1,'y_m':202609}
class RulesTest(unittest.TestCase):
 def decision(self,title,b='鱼跃',cat='制氧机',d=None):return classify(row(title,b,cat),d or {})
 def test_home_oxygen(self):self.assertEqual(self.decision('家用医用分子筛制氧机')['status'],'included')
 def test_pro_system(self):self.assertEqual(self.decision('医用分子筛制氧系统专业人员操作')['status'],'excluded')
 def test_hospital_same_is_not_professional(self):self.assertEqual(self.decision('医院同款家用医用压缩式雾化器',cat='雾化器')['status'],'included')
 def test_hospital_only_conflict(self):self.assertEqual(self.decision('医院专用家用医用压缩式雾化器',cat='雾化器')['status'],'included')
 def test_home_alone_not_medical(self):self.assertEqual(self.decision('家用制氧机')['status'],'included')
 def test_medical_alone_not_molecular(self):self.assertEqual(self.decision('家用医用制氧机')['status'],'included')
 def test_mesh_excluded(self):self.assertEqual(self.decision('家用医用网式雾化器',cat='雾化器')['status'],'excluded')
 def test_combination_not_system(self):self.assertEqual(self.decision('家用医用呼吸机与制氧机组合')['status'],'included')
 def test_accessory(self):self.assertEqual(self.decision('制氧机配件分子筛颗粒')['status'],'excluded')
 def test_bundled_mask(self):self.assertEqual(self.decision('家用医用压缩式雾化器C900+2套雾化面罩',b='欧姆龙',cat='雾化器')['status'],'included')
 def test_ambiguous_accessory(self):self.assertEqual(self.decision('家用医用压缩式雾化器雾化面罩',cat='雾化器')['status'],'included')
 def test_model_normalization(self):
  self.assertEqual(model_tokens('欧姆龙','NE-C900'),['C900'])
  self.assertEqual(model_tokens('鱼跃','403M'),['403M'])
  self.assertEqual(model_tokens('鱼跃','5L6L 8F-5AW'),['8F5AW'])
 def test_model_evidence_brand_scoped(self):
  d=build_dictionary([row('家用医用分子筛制氧机8F-5AW')])
  self.assertEqual(self.decision('家用制氧机8F-5AW',d=d)['status'],'included')
  self.assertEqual(self.decision('制氧机8F-5AW',b='其他厂家',d=d)['status'],'pending')
 def test_unknown_brand(self):self.assertIsNone(brand('其他 Other'))
 def test_brand_alias(self):self.assertEqual(brand('欧姆龙 Omron'),brand('欧姆龙'))
 def test_short_and_text_models(self):
  self.assertEqual(model_tokens('鱼跃','403H S6'),['403H','S6'])
  self.assertEqual(model_tokens('欧姆龙','NEC900 NE-C900'),['C900'])
  self.assertEqual(model_tokens('百瑞','PARI BOY Junior'),['BOYJUNIOR'])
 def test_same_link_and_conflict(self):
  a=row('家用制氧机');b=row('轻音氧气机');d=build_dictionary([a,b])
  self.assertEqual(classify(b,d)['basis'],'same_link')
  c=row('制氧机配件');d=build_dictionary([a,b,c])
  self.assertEqual(classify(b,d)['status'],'pending')
 def test_mixed_retained_under_home_policy(self):
  p=self.decision('家用医用压缩式雾化器雾化面罩',cat='雾化器')
  self.assertEqual(p['status'],'included');self.assertIsNotNone(p['mixed_reason'])
 def test_chinese_model_boundaries(self):
  self.assertEqual(model_tokens('百瑞','帕瑞BOY PRO儿童雾化器'),['BOYPRO'])
  self.assertEqual(model_tokens('可孚','523W Y525W KF10-5'),['KF105YW','KJRY523W','KJRY525W'])
  self.assertEqual(model_tokens('劲氧 ganityoung','YDD-5B/6B'),['YDD5B','YDD6B'])
 def test_model_then_link(self):
  a=row('家用制氧机K100');a['item_id']=2
  b=row('制氧机K100');c=row('轻音氧气机')
  d=build_dictionary([a,b,c]);self.assertEqual(classify(c,d)['status'],'included')
 def test_mesh_history_and_model_exclusion(self):
  a=row('家用网式雾化器M102',cat='雾化器');b=row('手持轻音',cat='雾化器')
  d=build_dictionary([a,b]);self.assertEqual(classify(b,d)['status'],'excluded')
  c=row('家用雾化器M102',cat='雾化器');c['item_id']=3
  self.assertEqual(classify(c,d)['status'],'excluded')
 def test_false_category_matches(self):
  for title in ['家用储雾罐','家用峰流速仪','医用电子口喷雾化器','潓美氢氧气机']:
   self.assertEqual(self.decision(title)['status'],'excluded')
 def test_identical_short_titles_are_link_scoped(self):
  a=row('家用制氧机');b=row('短标题');c=row('短标题');c['item_id']=2
  d=build_dictionary([a,b,c])
  self.assertEqual(classify(b,d)['status'],'included');self.assertEqual(classify(c,d)['status'],'pending')
  self.assertNotEqual(label_key(b),label_key(c))
if __name__=='__main__':unittest.main()
