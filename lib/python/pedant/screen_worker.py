#from threading import Thread
import threading
import thread
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import os,sys,json,hashlib,Image,ImageChops,ImageDraw,time,uuid,urllib2,shutil

class screen_worker(threading.Thread):

	browser = {}

	items = []

	timestamp = ''

	pathes = {}

	finished_ids = {}

	handled = False

	root = ''

	def __init__(self, browser, items, timestamp, data_storage_root ):

		super(screen_worker, self).__init__()
		#lol, copy require, i search this bug 3 hours :(
		self.browser = browser.copy()
		#launch browser
		if ( browser.has_key( 'wd_url' ) ):

			caps = getattr( DesiredCapabilities , self.browser['name'].upper() )
			if self.browser.has_key('desired_capabilities'):
				caps = dict( caps.items() + self.browser['desired_capabilities'].items() )
			#print caps
			try:
				self.browser['instance'] = webdriver.Remote(  
						command_executor=str(browser['wd_url']),
						desired_capabilities=caps,
						keep_alive=False )
			except urllib2.URLError:
				print browser
				raise ConnectionError( 'Can not connect to browser' )
		else:
			print 'Browser without wd_url in thread: '
			print browser
			thread.exit()

		self.browser['instance'].set_window_size( browser['window_size'][0],browser['window_size'][1] )
		self.items = list(items)
		self.timestamp = str(timestamp)
		self.root = data_storage_root
		self.pathes = self.calculatePathes()
		self.createFolders()

	"""
	run this
	@return void
	"""
	def run(self):

		for item in self.items:
			start_time = time.time()
			self.browser['instance'].get( item['url'] )
			item['load_time'] = round( time.time() - start_time , 2)
			#run all scripts
			for script in item['scripts']:
				self.browser['instance'].execute_script( script )
			#wait js conditions
			for wait_condition in item['wait_scripts']:
				w_time = 0
				while True:
					if self.browser['instance'].execute_script( script ) or w_time > 3:
						break
					time.sleep(1)
					w_time += 1
			#save actual screenshot
			self.browser['instance'].save_screenshot( self.pathes[ item['unid'] ]['abs']['actual_report_path'] )
			self.screen_processing( item )
			self.finished_ids[ item['unid'] ] = item['unid']
		self.browser['instance'].close
		#print "\nFinish browser " + self.browser['instance'].session_id
		return

	"""
	This function calculate pathes
	@return void
	"""
	def calculatePathes(self):
		# iterate items and calculate pathes
		pathes = {}
		for item in self.items:
			hvostik = item['unid'] + os.sep + self.browser['unid'] + os.sep
			pathes[ item['unid'] ] = {
				'abs': {
					'approved_dir': self.root + os.sep + 'approved' + os.sep + hvostik,
					'report_dir': self.root + os.sep + 'reports' + os.sep + self.timestamp + os.sep + hvostik,
					'approved_path': self.root + os.sep + 'approved' + os.sep + hvostik + 'approved.png',
					'actual_report_path': self.root + os.sep + 'reports' + os.sep + self.timestamp + os.sep + hvostik + 'actual.png',
					'approved_report_path': self.root + os.sep + 'reports' + os.sep + self.timestamp + os.sep + hvostik + 'approved_report.png',
					'diff_report_path': self.root + os.sep + 'reports' + os.sep + self.timestamp + os.sep + hvostik + 'diff.png', 
				}
			}
		return pathes

	"""
	This function create folders for items
	return void
	"""
	def createFolders(self):
		for item_unid,item_dict in self.pathes.iteritems():
				if ( os.path.isdir( item_dict['abs']['report_dir'] ) == False ):
					os.makedirs( item_dict['abs']['report_dir'] , 0777 )

	"""
	This function do work with taked screenshot
	@param item - dict with info about scanning item
	@param screenshot - png in string. Taked screenshot 
	"""
	def screen_processing(self, item ):
		#check actual screenshot
		if os.path.isfile( self.pathes[ item['unid'] ]['abs']['actual_report_path'] ):
			#try find approve screenshot
			if os.path.isfile( self.pathes[ item['unid'] ]['abs']['approved_path'] ):

				#if find - call compare screesnhots and copy approved to report folder
				compare_res = self.compare_screenshots(
					self.pathes[ item['unid'] ]['abs']['approved_path'],
					self.pathes[ item['unid'] ]['abs']['actual_report_path'],
					self.pathes[ item['unid'] ]['abs']['diff_report_path']
					)
				shutil.copyfile( self.pathes[ item['unid'] ]['abs']['approved_path'], self.pathes[ item['unid'] ]['abs']['approved_report_path'] )
				## if has diff - report error
				if ( compare_res ):
					self.save_result( "diff" , item )
				## else - report success
				else:
					self.save_result( "success", item )
			#have not approved
			else:
				self.save_result( "approve404", item )
		else:
			print "\n >>> ERROR: Can not save actual screenshot in: " + actual_path + "\n"
			return True

	def save_result(self,msg,item):
		#print "save result for file \n" 
		obj = open( self.pathes[item['unid']]['abs']['report_dir'] + os.sep + 'report.json' , 'wb')
		json.dump( {
				'item' : item,
				'browser' : { 'name': self.browser['name'], 'info' : self.browser['info'], 'unid':self.browser['unid'] },
				'window_size': self.browser['window_size'],
				'msg' : msg,
				}, 
				obj)
		obj.close

	"""
	This function compare two images and save difference in diff_path
	@param approved_path string - path to approved image
	@param actual_path string - path to actual image
	@param diff_path string - path to save difference image
	@return bool - True if images has a difference, and false if images the same
	"""
	def compare_screenshots(self,approved_path, actual_path, diff_path ):
		#
		dataA = open(approved_path, 'rb').read()
		dataB = open(actual_path, 'rb').read()

		if hashlib.md5(dataA).hexdigest() != hashlib.md5(dataB).hexdigest():
			#make one size
			# ToDo 
			imageA = Image.open(approved_path)
			imageB = Image.open(actual_path)
			#if sizes not match - resize smalled
			if ( imageA.size != imageB.size ):
				#get max image size
				w_size = max( [ imageA.size[0] , imageB.size[0] ] )
				h_size = max( [ imageA.size[1] , imageB.size[1] ] )
				#resize images with max size
				imageA = imageA.resize( [ w_size , h_size ] ,Image.ANTIALIAS )
				#imageA.size = [w_size , h_size]
				imageB = imageB.resize( [ w_size , h_size ] ,Image.ANTIALIAS )
				#imageB.size = [w_size , h_size]
			
			#calculate diff
			diff = ImageChops.difference(imageA, imageB)
			#generate pretty diff image  
			light = Image.new('RGB', size=imageA.size, color=0xFFFFFF)
			mask = Image.new('L', size=imageA.size, color=0xFF)
			draw = ImageDraw.Draw(mask)
			draw.rectangle((0, 0, imageA.size[0], imageA.size[1] ), fill=0x80)
			imageA = Image.composite(imageA, light, mask)
			imageA.paste(diff, (0,0), mask)
			imageA.convert("RGB")
			imageA.save( diff_path , "PNG" )
			return True
		return False


class ConnectionError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)