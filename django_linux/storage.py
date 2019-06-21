
from django.core.files.storage import FileSystemStorage
import os, zipfile, errno, shutil
from pprint import pprint
import hashlib
IRODS_PATH = "./irods/"

class LinuxStorage():
	def prepend_path(path):
		if (not os.path.exists(IRODS_PATH)):
			os.makedirs(IRODS_PATH)
		if( path[0] != "/" ):
			path = path[2:] if path[0:2] == "./" else path
			return IRODS_PATH + path
		else:
			return path

	@property
	def getUniqueTmpPath(self):
		pass
	
	def md5_checksum(self, file_name):
    		hash_md5 = hashlib.md5()
    		with open(fname, "rb") as f:
        		for chunk in iter(lambda: f.read(4096), b""):
            			hash_md5.update(chunk)
    		return hash_md5.hexdigest()
	
	def download(self, name):
		irods_name = self.prepend_path(name)
		return self.open(irods_name, mode="rb")
	
	def runBagitRule(self, rule_name, input_path, input_resouce):
		os.chdir(input_path)
		os.makedirs("data")
		self.copyFiles(input_resource, os.path.join(os.getcwd(), "data"))
	
		file = open("manifest-md5.txt", "w+")
		for subdir, dirs, files in os.walk(dir):
			for file in files:
				filename = os.path.join(subdir, file)
				file.write( self.md5_checksum(filename) + "    " +filename)
		file.close()

		file = open( "bagit.txt", "w+")
		file.write("BagIt-Version: 0.96\nTag-File-Character-Encoding: UTF-8\n")
		file.close()
	
		file = open("README.txt", "w+")
		file.write(README_TEXT)
		file.close()
	
		file = open("tagmanifest-md5.txt", "w+")
		files = [os.path.join(dir, f) for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]
		for file in files:
			file.write( self.md5_checksum(file) + "    " + file)
                
                output_path = input_path.split("/", 1)[1] + "/bags/" + input_path.split("/", 1)[0] + ".zip"
		self.zipup( input_path, output_path)

	def md5_checksum(self, filename):
		hash_md5 = hashlib.md5()
		with open(filename, "rb") as f:
			for chunk in iter(lambda: f.read(4096), b""):
				hash_md5.update(chunk)
		return hash_md5.hexdigest()
	
	def zipup(self, input_name, output_name):
                archive = zipfile.ZipFile(output_name, mode="w")
		archive.close()
        
	def unzip(self, zip_file_path, unzipped_folder=None):
                abs_path = os.path.dirname(zip_file_path)
                if not unzipped_folder:
                        unzipped_folder = os.path.splitext(os.path.basename(zip_file_path))[0].strip()

                unzipped_folder = self._get_nonexistant_path(os.path.join(abs_path, unzipped_folder))
                tar = tarfile.open(zip_file_path)
                for member in tar.getmembers():
                        tar.extract(member, path=unzipped_folder)
                        tar.close()
                return unzipped_folder

        def _get_nonexistant_path(self, path):
                if not os.path.exists(path):
                        return path
                i = 1
                new_path = "{}-{}".format(path, i)
                while os.path.exists(new_path):
                        i += 1
                        new_path = "{}-{}".format(path, i)
                return new_path
        '''
                What is AVU doing?
                setAVU -- stores the metadata associated with the file
                getAVU -- There is a lookup table for each one and its deafault value; check that and return the default value

                Alva: he will generate default AVUs for everything.
        '''
        def getAVU(self, name, attName):
                return False

        def setAVU(self, name, attName, attVal, attUnit=None):
                pass

        def ils_l(self, path): 
                pass

##########################################################################################################################
        def removeDirecotry(self, dirname):
                directory = self.prepend_path(dirname)
                if(os.path.isfile(directory)):
                        os.remove(directory)
                elif(os.path.isdir(directory)):
                        shutil.rmtree(directory)

        # copies files or directories recursively within irods
        def copyFiles(self, src_name, dest_name, ires=None):
                src_irods = self.prepend_path(src_name)
                dest_irods = self.prepend_path(dest_name)
                try:
                        shutil.copytree(src_irods, dest_irods)
                except FileExistsError as e: 
                        # if a dest_name is already present, create a directory within dest_name
                        dest_irods = dest_irods + "/" + src_irods.rsplit("/",1)[1]
                        shutil.copytree(src_irods, dest_irods)
                except NotADirectoryError as exc: 
                        # if copying a file, use shutil.copy
                        if(not os.path.exists(dest_irods.rsplit('/', 1)[0])):
                                os.makedirs(dest_irods.rsplit('/', 1)[0]) 
                        shutil.copy(src_irods, dest_irods)

        # moves (copy and remove the source directory) files or directories recursively
        def moveFile(self, src_name, dest_name):
                self.copyFiles(LinuxStorage, src_name, dest_name)
                self.removeDirecotry(LinuxStorage, src_name)
        
        # copies files or directories recursively from linux to irods
        def saveFile(self, from_name, to_name, create_directory=False, data_type_str=''):
                if create_directory == True:
                        splitted_directory = to_name.rsplit("/",1)
                        os.makedirs(splitted_directory[0])
                        if (len(splitted_directory) <= 0):
                                return
                else:
                        if from_name:
                                dest_irods = self.prepend_path(to_name)
                                try:
                                        shutil.copytree(from_name, dest_irods)
                                except FileExistsError as e: 
                                        # if a dest_name is already present, create a directory within dest_name
                                        dest_irods = dest_irods + "/" + from_name.rsplit("/",1)[1]
                                        shutil.copytree(from_name, dest_irods)
                                except NotADirectoryError as exc: 
                                        # if copying a file, use shutil.copy
                                        if(not os.path.exists(dest_irods.rsplit('/', 1)[0])):
                                                os.makedirs(dest_irods.rsplit('/', 1)[0]) 
                                        shutil.copy(from_name, dest_irods)

        # copies files or directories recursively from irods to linux
        def getFile(self, source_name, destination_name):
                src_irods = self.prepend_path(source_name)
                try:
                        shutil.copytree(src_irods, destination_name)
                except FileExistsError as e: 
                        # if a dest_name is already present, create a directory within dest_name
                        destination_name = destination_name + "/" + src_irods.rsplit("/",1)[1]
                        shutil.copytree(src_irods, destination_name)
                except NotADirectoryError as exc: 
                        # if copying a file, use shutil.copy
                        if(not os.path.exists(destination_name.rsplit('/', 1)[0])):
                                os.makedirs(destination_name.rsplit('/', 1)[0]) 
                        shutil.copy(src_irods, destination_name)
