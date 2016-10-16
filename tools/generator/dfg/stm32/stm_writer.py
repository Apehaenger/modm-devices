# -*- coding: utf-8 -*-
# Copyright (c) 2013-2016, Niklas Hauser
# Copyright (c)      2016, Fabian Greif
# All rights reserved.

import itertools
import logging

from ..writer import XMLDeviceWriter

LOGGER = logging.getLogger('dfg.stm.writer')

class STMDeviceWriter(XMLDeviceWriter):
    """ STMDeviceWriter
    Translates the Device to a XPCC specific format.
    """
    def __init__(self, device):
        XMLDeviceWriter.__init__(self, device)

        self.addDeviceAttributesToNode(self.root, 'flash')
        self.addDeviceAttributesToNode(self.root, 'ram')
        self.addDeviceAttributesToNode(self.root, 'core')

        self.addDeviceAttributesToNode(self.root, 'pin-count')

        self.addDeviceAttributesToNode(self.root, 'header')
        self.addDeviceAttributesToNode(self.root, 'define')

        core_child = self.root.addChild('driver')
        core_child.setAttributes({'type': 'core', 'name': 'cortex'})

        # Memories
        self.addMemoryToNode(core_child)
        self.addInterruptTableToNode(core_child)

        adc_map = {'f0': 'stm32f0',
                   'f1': 'stm32f1',
                   'f2': 'stm32f2',
                   'f3': 'stm32f3',
                   'f4': 'stm32',
                   'f7': 'stm32'}
        # ADC
        if self.device.id.family == 'f3' and self.device.id.name == '373':
            self.addModuleAttributesToNode(self.root, 'ADC', 'adc', 'stm32')
        else:
            self.addModuleAttributesToNode(self.root, 'ADC', 'adc', adc_map[self.device.id.family])
        # CAN
        self.addModuleAttributesToNode(self.root, 'CAN', 'can')
        # Clock
        clock_child = self.root.addChild('driver')
        clock_child.setAttributes({'type': 'clock', 'name': 'stm32'})
        # DAC
        # self.addModuleAttributesToNode(self.root, 'DAC', 'dac')
        if (self.device.id.family in ['f3', 'f4']):
            # DMA
            self.addModuleAttributesToNode(self.root, 'DMA', 'dma')
        # FSMC
        self.addModuleAttributesToNode(self.root, 'FSMC', 'fsmc')
        self.addModuleAttributesToNode(self.root, 'FMC', 'fsmc')
        # I2C
        self.addModuleAttributesToNode(self.root, 'I2C', 'i2c')
        # ID
        self.addModuleAttributesToNode(self.root, 'ID', 'id')
        # Random
        self.addModuleAttributesToNode(self.root, 'RNG', 'random')
        # SPI
        self.addModuleAttributesToNode(self.root, 'SPI', 'spi')
        self.addModuleAttributesToNode(self.root, ['UART', 'USART'], 'spi', 'stm32_uart')
        # Timer
        self.addModuleAttributesToNode(self.root, 'TIM', 'timer')
        # UART
        self.addModuleAttributesToNode(self.root, ['UART', 'USART'], 'uart')
        # USB
        self.addModuleAttributesToNode(self.root, ['OTG_FS_DEVICE', 'USB_FS', 'OTG_FS', 'USB'], 'usb', 'stm32_fs')
        # GPIO
        self.addGpioToNode(self.root)


    def addDeviceAttributesToNode(self, node, name):
        properties = self.device.getProperty(name)

        if properties == None:
            return

        for prop in properties.values:
            for device_id in prop.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                child = node.addChild(name)
                child.setAttributes(attr)
                if isinstance(prop.value, list):
                    child.setValue(prop.value[0])
                else:
                    child.setValue(prop.value)

    def addModuleAttributesToNode(self, node, peripheral, name, family=None):
        if family == None:
            family = 'stm32'
        modules = self.device.getProperty('modules')

        peripherals = []
        if isinstance(peripheral, list):
            peripherals.extend(peripheral)
        else:
            peripherals.append(peripheral)

        driver = node.addChild('driver')
        driver.setAttributes({'type': name, 'name': family})

        for prop in modules.values:
            instances = []
            found = False
            for p in peripherals:
                for module in [m for m in prop.value if m.startswith(p)]:
                    found = True
                    inst = module[len(p):]
                    if inst != '' and inst.isdigit():
                        instances.append(inst)

            if not found:
                continue
            instances.sort(key=int)

            for device_id in prop.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                self.addInstancesToDriver(driver, instances, attr)

    def addMemoryToNode(self, node):
        memories = self.device.getProperty('memories')

        for mem in memories.values:
            sections = mem.value

            for device_id in mem.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                for section in sections:
                    memory_section = node.addChild('memory')
                    memory_section.setAttributes(attr)
                    memory_section.setAttributes(section)
        # sort the node children by start address
        # node.sort(key=lambda k: (int(k.get('start'), 16)))

    @staticmethod
    def sortNode(k):
        if k.tag not in ['vector', 'memory']:
            return -1
        return (k.tag, int(k.get('position')) if k.get('position') else (k.tag, int(k.get('start'), 16), int(k.get('size'))))

    def addInterruptTableToNode(self, node):
        interrupts = self.device.getProperty('interrupts')

        for interrupt in interrupts.values:
            vectors = interrupt.value

            for device_id in interrupt.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                for vec in vectors:
                    vector_section = node.addChild('vector')
                    vector_section.setAttributes(attr)
                    vector_section.setAttributes(vec)
        # sort the node children by vector number
        node.sort(key=STMDeviceWriter.sortNode)

    def addGpioToNode(self, node):
        props = self.device.getProperty('gpios')

        driver = node.addChild('driver')
        driver.setAttributes({'type': 'gpio', 'name': 'stm32f1' if self.device.id.family == 'f1' else 'stm32'})

        for prop in props.values:
            gpios = prop.value

            for device_id in prop.ids.differenceFromIds(self.device.ids):
                attr = self._getAttributeDictionaryFromId(device_id)
                for gpio in gpios:
                    gpio_child = driver.addChild('gpio')
                    gpio_child.setAttributes(attr)
                    gpio_child.setAttributes(gpio)
                    # search for alternate functions
                    matches = []
                    for af_property in self.device.getProperty('gpio_afs').values:
                        for af in af_property.value:
                            if af['gpio_port'] == gpio['port'] and af['gpio_id'] == gpio['id']:
                                differences = af_property.ids.differenceFromIds(prop.ids)
                                matches.append({'af': dict(af), 'differences': differences})
                    for af_dict in matches:
                        for af_id in af_dict['differences']:
                            af_attr = self._getAttributeDictionaryFromId(af_id)
                            af_child = gpio_child.addChild('af')
                            af_child.setAttributes(af_attr)
                            for key in ['id', 'peripheral', 'name', 'type'] :
                                if key in af_dict['af']:
                                    af_child.setAttribute(key, af_dict['af'][key])
                    gpio_child.sort(key=lambda k : (int(1e6 if (k.get('id') == None) else k.get('id').split(',')[0]), k.get('peripheral')))
        # sort the node children by port and id
        driver.sort(key=lambda k : (k.get('port'), int(k.get('id'))))

    def _hasCoreCoupledMemory(self):
        for memory in [memory.value for memory in self.device.getProperty('memories').values]:
            if any(mem['name'] == 'ccm' for mem in memory):
                return True
        return False

    def _getAttributeDictionaryFromId(self, device_id):
        target = device_id.properties
        device_dict = {}
        for attr in target:
            if target[attr] != None:
                if attr == 'size_id':
                    device_dict['device-size-id'] = target[attr]
                if attr == 'name':
                    device_dict['device-name'] = target[attr]
                if attr == 'pin_id':
                    device_dict['device-pin-id'] = target[attr]
        return device_dict

    def _addNamingSchema(self):
        identifiers = list(itertools.product(("stm32f",),
                                             self.device.ids.getAttribute('name'),
                                             self.device.ids.getAttribute('pin_id'),
                                             self.device.ids.getAttribute('size_id')))
        devices = [d.string for d in self.device.ids]
        for identifier_parts in identifiers:
            identifier = ''.join(identifier_parts)

            if identifier not in devices:
                child = self.root.prependChild('invalid-device')
                child.setValue(identifier)
            else:
                devices.remove(identifier)

        for device in devices:
            LOGGER.error("Found device not matching naming schema: '{}'".format(device))

        child = self.root.prependChild('naming-schema')
        child.setValue('{{ platform }}f{{ name }}{{ pin_id }}{{ size_id }}')

    def write(self, folder):
        self._addNamingSchema()

        file_name = 'stm32f' + '_'.join(self.device.ids.getAttribute('name'))
        file_name += '-' + '_'.join(self.device.ids.getAttribute('pin_id'))
        file_name += '-' + '_'.join(self.device.ids.getAttribute('size_id'))
        self.writeToFolder(folder, file_name + '.xml')

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "STMDeviceWriter(\n" + self.toString() + ")"
