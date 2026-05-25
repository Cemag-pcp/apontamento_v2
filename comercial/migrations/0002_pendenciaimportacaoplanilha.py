from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendenciaImportacaoPlanilha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ped_ufpessoaop_regiao_nome', models.CharField(db_column='PED_UFPESSOAOP.REGIAO.NOME', max_length=100)),
                ('ped_pessoa_uf_codigo', models.CharField(db_column='PED_PESSOA.UF.CODIGO', max_length=10)),
                ('ped_observacao', models.TextField(blank=True, db_column='PED_OBSERVACAO')),
                ('ped_pessoa_localidade_codigo', models.CharField(db_column='PED_PESSOA.LOCALIDADE.CODIGO', max_length=100)),
                ('ped_chcriacao', models.CharField(db_column='PED_CHCRIACAO', max_length=50)),
                ('ped_emissao', models.DateField(db_column='PED_EMISSAO')),
                ('ped_previsaoemissaodoc', models.DateField(db_column='PED_PREVISAOEMISSAODOC')),
                ('ped_programaca', models.DateField(db_column='PED_PROGRAMACA')),
                ('ped_classe_nome', models.CharField(db_column='PED_CLASSE.NOME', max_length=150)),
                ('ped_pessoa_codigo', models.CharField(db_column='PED_PESSOA.CODIGO', max_length=150)),
                ('ped_recurso_codigo', models.CharField(db_column='PED_RECURSO.CODIGO', max_length=100)),
                ('ped_recurso_nome', models.TextField(db_column='PED_RECURSO.NOME')),
                ('ped_recurso_classe_nome', models.CharField(db_column='PED_RECURSO.CLASSE.NOME', max_length=150)),
                ('ped_numeroserie', models.CharField(blank=True, db_column='PED_NUMEROSERIE', max_length=100)),
                ('ped_nucleo_codigo', models.CharField(db_column='PED_NUCLEO.CODIGO', max_length=100)),
                ('ped_quantidade', models.DecimalField(db_column='PED_QUANTIDADE', decimal_places=4, max_digits=18)),
                ('ped_unitario', models.DecimalField(db_column='PED_UNITARIO', decimal_places=4, max_digits=18)),
                ('ped_total', models.DecimalField(db_column='PED_TOTAL', decimal_places=4, max_digits=18)),
                ('ped_recurso_descricaogenerica', models.CharField(db_column='PED_RECURSO.DESCRICAOGENERICA', max_length=150)),
                ('ped_representa_codigo', models.CharField(db_column='PED_REPRESENTA.CODIGO', max_length=150)),
                ('ped_idnegociacao', models.CharField(db_column='PED_IDNEGOCIACAO', max_length=50)),
            ],
            options={
                'verbose_name': 'Pendência para Importação na Planilha',
                'verbose_name_plural': 'Pendências para Importação na Planilha',
                'db_table': 'comercial_pendencia_importacao_planilha',
            },
        ),
        migrations.AddConstraint(
            model_name='pendenciaimportacaoplanilha',
            constraint=models.UniqueConstraint(fields=('ped_idnegociacao', 'ped_chcriacao', 'ped_recurso_codigo', 'ped_numeroserie'), name='unique_pend_import_planilha_item'),
        ),
    ]
