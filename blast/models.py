from django.db import models
from filebrowser.fields import FileBrowseField
from django.core.urlresolvers import reverse
import os.path
from django.conf import settings

class BlastQueryRecord(models.Model):
    task_id = models.CharField(max_length=32, primary_key=True) # ex. 128c8661c25d45b8-9ca7809a09619db9
    enqueue_date = models.DateTimeField(auto_now_add=True)
    dequeue_date = models.DateTimeField(null=True)
    result_date = models.DateTimeField(null=True)
    result_status = models.CharField(max_length=32, default='WAITING') # ex. WAITING, SUCCESS, NO_ASN, ASN_EMPTY, NO_CSV, CSV_EMPTY

    def __unicode__(self):
        return self.task_id

    def get_absolute_url(self):
        return reverse('blast:retrieve', args=[str(self.task_id)])

    class Meta:
        verbose_name = 'BLAST result'

class OrganismManager(models.Manager):
    def get_by_natural_key(self, short_name):
        return self.get(short_name=short_name)

class Organism(models.Model):
    objects = OrganismManager()
    display_name = models.CharField(max_length=200, unique=True, help_text='Scientific or common name') # shown to user
    short_name = models.CharField(max_length=20, unique=True, help_text='This is used for file names and variable names in code') # used in code or filenames
    description = models.TextField(blank=True) # optional
    tax_id = models.PositiveIntegerField('NCBI Taxonomy ID', null=True, blank=True, help_text='This is passed into makeblast') # ncbi tax id
    
    def natural_key(self):
        return (self.short_name,)

    def __unicode__(self):
        return self.display_name

class BlastDbTypeManager(models.Manager):
    def get_by_natural_key(self, dataset_type):
        return self.get(dataset_type=dataset_type)

class BlastDbType(models.Model):
    objects = BlastDbTypeManager()
    molecule_type = models.CharField(max_length=4, default='nucl', choices=(
        ('nucl', 'Nucleotide'),
        ('prot', 'Protein'))) # makeblastdb -dbtype
    dataset_type = models.CharField(max_length=50, unique=True) # 
    
    def natural_key(self):
        return (self.dataset_type,)

    def __unicode__(self):
        return u'%s - %s' % (self.get_molecule_type_display(), self.dataset_type)

    class Meta:
        verbose_name = 'BLAST database type'

class BlastDbManager(models.Manager):
    def get_by_natural_key(self, fasta_file):
        return self.get(fasta_file=fasta_file)

class BlastDb(models.Model):
    objects = BlastDbManager()
    organism = models.ForeignKey(Organism) # 
    type = models.ForeignKey(BlastDbType) # 
    #fasta_file = models.FileField(upload_to='blastdb') # upload file
    fasta_file = FileBrowseField('FASTA file', max_length=100, directory='blastdb/', extensions='FASTA', format='FASTA')
    title = models.CharField(max_length=200, unique=True, help_text='This is passed into makeblast -title') # makeblastdb -title
    description = models.TextField(blank=True) # shown in blast db selection ui
    is_shown = models.BooleanField(default=None, help_text='Display this database in the BLAST submit form') # to temporarily remove from blast db selection ui
    #sequence_count = models.PositiveIntegerField(null=True, blank=True) # number of sequences in this fasta
    
    # properties
    def fasta_file_exists(self):
        return os.path.isfile(self.fasta_file.path_full)
    fasta_file_exists.boolean = True
    fasta_file_exists.short_description = 'file exists'

    def makeblastdb(self):
        if not os.path.isfile(self.fasta_file.path_full):
            return 1, 'FASTA file not found', ''
        from sys import platform
        from subprocess import Popen, PIPE
        bin_name = 'bin_linux'
        if platform == 'win32':
            bin_name = 'bin_win'
        makeblastdb_path = os.path.join(settings.PROJECT_ROOT, 'blast', bin_name, 'makeblastdb')
        args = [makeblastdb_path, '-in', self.fasta_file.path_full, '-dbtype', self.type.molecule_type, '-hash_index']
        if self.title:
            args += ['-title', self.title]
        if self.organism.tax_id:
            args += ['-taxid', str(self.organism.tax_id)]
        p = Popen(args, stdout=PIPE, stderr=PIPE)
        output, error = p.communicate()
        return p.returncode, error, output

    def natural_key(self):
        return (str(self.fasta_file),)

    def __unicode__(self):
        return str(self.fasta_file)

    class Meta:
        verbose_name = 'BLAST database'

class Sequence(models.Model):
    'Contents of this table should be automatically generated'
    key = models.AutoField(primary_key=True)
    blast_db = models.ForeignKey(BlastDb, verbose_name='BLAST DB') # 
    id = models.CharField(max_length=100) # 
    header = models.CharField(max_length=400) # 
    length = models.PositiveIntegerField() # 
    sequence = models.TextField() # 

    def __unicode__(self):
        return self.id

    class Meta:
        unique_together = ('blast_db', 'id')

class JbrowseSetting(models.Model):
    'Used to link databases to Jbrowse'
    blast_db = models.ForeignKey(BlastDb, verbose_name='reference', unique=True, help_text='The BLAST database used as the reference in Jbrowse') # 
    url = models.URLField('Jbrowse URL', unique=True, help_text='The URL to Jbrowse using this reference')

    def __unicode__(self):
        return self.url
